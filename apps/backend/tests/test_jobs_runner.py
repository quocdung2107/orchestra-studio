from __future__ import annotations

import asyncio
import threading
import time
import uuid

import pytest
from sqlalchemy import select

from orchestra_backend.jobs.engines import EngineManager, EngineSpec
from orchestra_backend.jobs.models import Job
from orchestra_backend.jobs.runner import JobError, JobRunner, enqueue
from orchestra_backend.jobs.scheduler import ResourceReq, ResourceScheduler


class Recorder:
    def __init__(self, kind: str, req: ResourceReq, sleep: float = 0.05, fail_times: int = 0):
        self.kind = kind
        self.req = req
        self.sleep = sleep
        self.fail_times = fail_times
        self.active = 0
        self.max_active = 0
        self.calls = 0
        self.lock = threading.Lock()

    def resources(self, job, c):
        return self.req

    def run(self, ctx):
        with self.lock:
            self.calls += 1
            self.active += 1
            self.max_active = max(self.max_active, self.active)
            n = self.calls
        time.sleep(self.sleep)
        with self.lock:
            self.active -= 1
        if n <= self.fail_times:
            raise JobError("flaky", "transient")
        return {"n": n}


def make_runner(container, *, max_parallel=2, ram=lambda: 8000, engines=None, cpu_slots=4):
    engines = engines or EngineManager([], log_dir=container.settings.data_dir / "logs")
    sched = ResourceScheduler(
        max_parallel=max_parallel,
        cpu_slots=cpu_slots,
        engines=engines,
        ram_probe=ram,
        vram_probe=lambda: 4000,
    )
    return JobRunner(container, sched, engines, lease_s=5, poll_s=0.05, retry_backoff_s=0)


def add_jobs(container, company_id, kind, n, **kw):
    with container.tx() as s:
        return [
            enqueue(s, company_id=uuid.UUID(company_id), kind=kind, payload={"i": i}, **kw).id
            for i in range(n)
        ]


def statuses(container, ids):
    with container.tx() as s:
        return [s.get(Job, i).status for i in ids]


def test_idempotency_key_returns_existing_job(container, company):
    with container.tx() as s:
        a = enqueue(
            s, company_id=uuid.UUID(company["id"]), kind="x", payload={}, idempotency_key="k1"
        )
        b = enqueue(
            s, company_id=uuid.UUID(company["id"]), kind="x", payload={}, idempotency_key="k1"
        )
        assert a.id == b.id


def test_two_gpu_jobs_never_run_together_but_cpu_jobs_can(container, company):
    runner = make_runner(container, max_parallel=3)
    gpu = Recorder("gpu.work", ResourceReq(device="gpu", exclusive_gpu=True), sleep=0.1)
    cpu = Recorder("cpu.work", ResourceReq(device="cpu"), sleep=0.1)
    runner.register(gpu)
    runner.register(cpu)
    ids = add_jobs(container, company["id"], "gpu.work", 3) + add_jobs(
        container, company["id"], "cpu.work", 3
    )
    asyncio.run(runner.drain(30))
    assert statuses(container, ids) == ["succeeded"] * 6
    assert gpu.max_active == 1
    assert cpu.max_active >= 2


def test_retry_then_fail_after_max_attempts(container, company):
    runner = make_runner(container)
    flaky = Recorder("flaky", ResourceReq(device="none"), sleep=0, fail_times=1)
    runner.register(flaky)
    ok_id = add_jobs(container, company["id"], "flaky", 1, max_attempts=2)[0]
    asyncio.run(runner.drain(10))
    assert statuses(container, [ok_id]) == ["succeeded"]

    always = Recorder("always", ResourceReq(device="none"), sleep=0, fail_times=99)
    runner.register(always)
    bad = add_jobs(container, company["id"], "always", 1, max_attempts=2)[0]
    asyncio.run(runner.drain(10))
    with container.tx() as s:
        job = s.get(Job, bad)
        assert job.status == "failed" and job.attempts == 2 and job.error_code == "flaky"


def test_memory_gate_stops_idle_engine_then_runs(container, company, tmp_path):
    free = {"mb": 1000}
    stopped = []

    class FakeEngines(EngineManager):
        def stop_idle(self, exclude=None):
            if stopped:
                return False
            stopped.append(True)
            free["mb"] = 6000  # the idle engine's RAM came back
            return True

        def is_warm(self, engine_id):
            return False

    engines = FakeEngines([], log_dir=tmp_path)
    runner = make_runner(container, ram=lambda: free["mb"], engines=engines)
    heavy = Recorder("heavy", ResourceReq(device="cpu", est_ram_mb=3000), sleep=0)
    runner.register(heavy)
    jid = add_jobs(container, company["id"], "heavy", 1)[0]
    asyncio.run(runner.drain(10))
    assert stopped and statuses(container, [jid]) == ["succeeded"]


def test_insufficient_memory_defers_instead_of_running(container, company):
    runner = make_runner(container, ram=lambda: 600)
    heavy = Recorder("heavy", ResourceReq(device="cpu", est_ram_mb=3000), sleep=0)
    runner.register(heavy)
    jid = add_jobs(container, company["id"], "heavy", 1)[0]
    asyncio.run(runner.tick())
    with container.tx() as s:
        job = s.get(Job, jid)
        assert job.status == "queued" and job.deferrals == 1
        assert "RAM" in job.progress_note
    assert heavy.calls == 0


def test_job_left_running_by_dead_process_is_resumed(container, company):
    jid = add_jobs(container, company["id"], "resume.me", 1)[0]
    with container.tx() as s:  # simulate a crash mid-job
        job = s.get(Job, jid)
        job.status = "running"
        job.attempts = 1
    runner = make_runner(container)
    rec = Recorder("resume.me", ResourceReq(device="none"), sleep=0)
    runner.register(rec)
    assert runner.recover() == 1
    asyncio.run(runner.drain(10))
    assert statuses(container, [jid]) == ["succeeded"] and rec.calls == 1


def test_cancel_queued_job_and_retry_endpoint(client, container, company):
    jid = add_jobs(container, company["id"], "never", 1)[0]
    r = client.post(f"/api/v1/jobs/{jid}/cancel")
    assert r.json()["status"] == "cancelled"
    r = client.post(f"/api/v1/jobs/{jid}/retry")
    assert r.json()["status"] == "queued"
    r = client.get(f"/api/v1/companies/{company['id']}/jobs")
    assert any(j["id"] == str(jid) for j in r.json())


def test_engine_manager_external_engine_unavailable(tmp_path):
    from orchestra_backend.jobs.engines import EngineUnavailable

    m = EngineManager(
        [EngineSpec(id="vieneu", base_url="http://127.0.0.1:1", install_hint="hãy mở")],
        log_dir=tmp_path,
        health=lambda s: False,
    )
    with pytest.raises(EngineUnavailable, match="hãy mở"):
        m.ensure_running("vieneu")


def test_engine_spec_must_be_loopback():
    with pytest.raises(ValueError):
        EngineSpec(id="x", base_url="http://192.168.1.5:8000")


def test_engine_manager_starts_and_stops_managed_process(tmp_path):
    import sys

    flag = tmp_path / "up"
    script = tmp_path / "srv.py"
    script.write_text(
        "import time,pathlib,sys\npathlib.Path(sys.argv[1]).write_text('1')\ntime.sleep(60)\n"
    )
    spec = EngineSpec(
        id="fake", base_url="http://127.0.0.1:9", command=[sys.executable, str(script), str(flag)]
    )
    m = EngineManager([spec], log_dir=tmp_path, start_timeout_s=10, health=lambda s: flag.exists())
    assert m.acquire("fake") == "http://127.0.0.1:9"
    assert m.is_managed_alive("fake")
    m.release("fake")  # keep_warm 0 -> stopped right away
    assert not m.is_managed_alive("fake")


def test_jobs_listed_in_order(container, company):
    add_jobs(container, company["id"], "x", 3)
    with container.tx() as s:
        assert len(list(s.scalars(select(Job).where(Job.kind == "x")))) == 3
