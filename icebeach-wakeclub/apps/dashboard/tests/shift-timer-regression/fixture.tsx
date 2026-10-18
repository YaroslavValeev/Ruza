import { useState } from "react";
import { createRoot } from "react-dom/client";
import { MemoryRouter } from "react-router-dom";
import { LiveShiftStrip } from "../../src/components/shift-timer/LiveShiftStrip";
import { PilotRideControls } from "../../src/components/shift-timer/PilotRideControls";
import * as timer from "../../src/lib/shift-timer";
import { getToday } from "../../src/mobile/pilot-utils";
import type { BookingItem, StaffRole } from "../../src/types";
import "../../src/index.css";

const initialBooking = {
  booking_id: "qa-ride", status: "ready", timer_state: "idle", warmup_state: "warmed_up",
  remaining_seconds: 305, planned_duration_minutes: 25, actual_duration_seconds: 0,
  client_name: "Mock rider", client_id: "mock-client", time: "12:00", boat_id: "mock-boat",
} as BookingItem;

type Config = { role: StaffRole; booking: BookingItem; allowTimer: boolean; allowCancel: boolean };
let renderConfig: (config: Config) => void;
const pending: Array<{ resolve: (booking: BookingItem) => void; reject: (error: Error) => void; bookingId: string; action: string }> = [];

const qa = {
  timer,
  getToday,
  calls: [] as Array<{ bookingId: string; action: string }>,
  liveCalls: 0,
  liveBooking: { ...initialBooking, status: "in_progress", timer_state: "running" } as BookingItem | null,
  reset(role: StaffRole, status: BookingItem["status"], timerState: BookingItem["timer_state"], allowTimer = true, allowCancel = true) {
    if (pending.length) throw new Error("Finish pending mocks before resetting the fixture");
    this.calls = [];
    renderConfig({ role, booking: { ...initialBooking, status, timer_state: timerState }, allowTimer, allowCancel });
  },
  getLive() {
    this.liveCalls += 1;
    return Promise.resolve({ focus_booking: this.liveBooking ? { ...this.liveBooking } : null });
  },
  mutate(bookingId: string, action: string) {
    this.calls.push({ bookingId, action });
    return new Promise<BookingItem>((resolve, reject) => pending.push({ resolve, reject, bookingId, action }));
  },
  finish(fail = false) {
    const request = pending.shift();
    if (!request) throw new Error("No pending mock action");
    if (fail) return request.reject(new Error("Mock request failed"));
    const transitions = {
      start: { status: "in_progress", timer_state: "running" },
      pause: { status: "in_progress", timer_state: "paused" },
      stop: { status: "done", timer_state: "completed", actual_duration_seconds: 75 },
      no_show: { status: "no_show" }, cancelled: { status: "cancelled" },
      arrived: { status: "arrived" }, late: { status: "late" },
    };
    request.resolve({ ...initialBooking, booking_id: request.bookingId, ...transitions[request.action as keyof typeof transitions] } as BookingItem);
  },
};

declare global { interface Window { shiftQa: typeof qa; } }
window.shiftQa = qa;

function Fixture() {
  const [config, setConfig] = useState<Config>({ role: "pilot", booking: initialBooking, allowTimer: true, allowCancel: true });
  renderConfig = setConfig;
  const session = { role: config.role, club_id: "mock-club", staff_user_id: "mock-staff", full_name: "Mock staff" };
  return (
    <main data-role={config.role} data-status={config.booking.status} data-state={config.booking.timer_state} className="mx-auto max-w-5xl space-y-4 p-3">
      <LiveShiftStrip session={session} compact />
      {["focus", "duplicate", "other"].map((id) => (
        <section key={id} data-testid={id} className="game-panel p-3">
          <PilotRideControls
            session={session}
            booking={id === "other" ? { ...initialBooking, booking_id: "other-ride" } : config.booking}
            onUpdated={(booking) => { if (id !== "other") setConfig((value) => ({ ...value, booking })); }}
            allowTimerControls={config.allowTimer}
            allowCancel={config.allowCancel}
            compact
          />
        </section>
      ))}
    </main>
  );
}

// LiveShiftStrip ставит ссылку «Открыть бронь» через react-router — в приложении роутер есть всегда.
createRoot(document.getElementById("root")!).render(<MemoryRouter><Fixture /></MemoryRouter>);
