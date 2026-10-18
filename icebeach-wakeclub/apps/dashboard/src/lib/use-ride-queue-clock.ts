import { useCallback, useEffect, useState } from "react";

import { BookingItem, PilotQueueItem } from "../types";
import { mergeBookingUpdate } from "./equipment";
import { getLiveRemainingSeconds } from "./shift-timer";

export function useRideQueueClock() {
  const [items, setItems] = useState<PilotQueueItem[]>([]);
  const [receivedAt, setReceivedAt] = useState<Record<string, number>>({});
  const [now, setNow] = useState(Date.now);

  useEffect(() => {
    const interval = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(interval);
  }, []);

  const setQueue = useCallback((rows: PilotQueueItem[]) => {
    const timestamp = Date.now();
    setItems(rows);
    setReceivedAt(Object.fromEntries(rows.map((row) => [row.booking_id, timestamp])));
    setNow(timestamp);
  }, []);

  const mergeItem = useCallback((updated: BookingItem) => {
    const timestamp = Date.now();
    setItems((rows) => rows.map((row) => row.booking_id === updated.booking_id ? mergeBookingUpdate(row, updated) : row));
    // A mutation rebases only its booking; other running rides keep their anchor.
    setReceivedAt((anchors) => ({ ...anchors, [updated.booking_id]: timestamp }));
    setNow(timestamp);
  }, []);

  const remainingSeconds = (row: PilotQueueItem) => getLiveRemainingSeconds(row, receivedAt[row.booking_id] ?? now, now);
  return { items, setQueue, mergeItem, remainingSeconds };
}
