import type { EventEnvelope } from "@orchestra/contracts";
import { useEffect, useRef } from "react";
import { describeEvent } from "../live/eventLog";
import type { StreamStatus } from "../live/useEventStream";
import { useSelection } from "../state/selection";
import { formatTime } from "./ui";

const STATUS_LABEL: Record<StreamStatus, string> = {
  connecting: "đang kết nối",
  open: "trực tiếp",
  reconnecting: "mất kết nối, đang thử lại",
  closed: "chưa kết nối",
};

export function ActivityConsole(props: {
  events: EventEnvelope[];
  status: StreamStatus;
  open: boolean;
  onToggle: () => void;
}) {
  const { select } = useSelection();
  const bottom = useRef<HTMLDivElement>(null);
  useEffect(() => {
    bottom.current?.scrollIntoView?.({ block: "end" });
  }, [props.events.length]);

  return (
    <div className="border-t border-slate-800 bg-slate-950">
      <button
        onClick={props.onToggle}
        className="w-full flex items-center justify-between px-4 py-1.5 text-xs text-slate-400 hover:bg-slate-900"
      >
        <span>
          Activity Console · {props.events.length} sự kiện ·{" "}
          <span className={props.status === "open" ? "text-emerald-400" : "text-amber-400"}>
            {STATUS_LABEL[props.status]}
          </span>
        </span>
        <span>{props.open ? "Thu gọn ▾" : "Mở ▴"}</span>
      </button>
      {props.open && (
        <div className="h-48 overflow-auto font-mono text-xs px-4 pb-2" data-testid="console">
          {props.events.length === 0 && <p className="text-slate-500 py-2">Chưa có sự kiện.</p>}
          {props.events.map((e) => (
            <div key={e.sequence} className="flex gap-3 py-0.5">
              <span className="text-slate-500 w-10 text-right">#{e.sequence}</span>
              <span className="text-slate-500 w-20">{formatTime(e.occurred_at)}</span>
              <span className={`w-48 ${e.event_type.endsWith("failed") ? "text-red-400" : "text-indigo-300"}`}>
                {e.event_type}
              </span>
              <span className="text-slate-500 w-32 truncate">{e.source}</span>
              {e.run_id ? (
                <button className="text-left hover:underline flex-1 truncate" onClick={() => select({ kind: "run", id: e.run_id! })}>
                  {describeEvent(e)}
                </button>
              ) : (
                <span className="flex-1 truncate">{describeEvent(e)}</span>
              )}
            </div>
          ))}
          <div ref={bottom} />
        </div>
      )}
    </div>
  );
}
