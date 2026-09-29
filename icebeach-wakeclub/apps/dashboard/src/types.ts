export type StaffRole = "admin" | "operator" | "pilot" | "coach" | "marketing_read";
export type BookingStatus = "confirmed" | "arrived" | "ready" | "in_progress" | "done" | "late" | "no_show" | "cancelled";
export type WetsuitSize = "XS" | "S" | "M" | "L" | "XL" | "XXL";
export type WetsuitGender = "male" | "female";
export type RideType = "wakeboard" | "surf" | "skim";
export type KpiPeriod = "day" | "week" | "month" | "season" | "custom";
export type PaymentMethod = "cash" | "card_terminal" | "sbp" | "online";
export type PaymentStatus = "unpaid" | "partially_paid" | "paid" | "overpaid" | "partially_refunded" | "refunded";
export type PreflightLevel = "PASS" | "WARN" | "BLOCKER";
export type SmokeLevel = "PASS" | "FAIL";

export type StaffSession = {
  token?: string;
  staff_user_id: string;
  role: StaffRole;
  full_name: string;
  club_id: string;
  phone?: string;
  boat_id?: string | null;
};

export type LoginCodeResponse = {
  delivery_channel: string;
  expires_in_seconds: number;
  debug_code?: string | null;
  staff_user_id?: string | null;
  full_name?: string | null;
};

export type KpiRideBreakdownItem = {
  ride_type: RideType;
  sessions_count: number;
  revenue_estimate: number;
};

export type KpiTimelinePoint = {
  date: string;
  sessions_count: number;
  revenue_estimate: number;
  utilization_pct: number;
};

export type KpiPlanFact = {
  sessions_target?: number | null;
  utilization_target_pct?: number | null;
  revenue_target?: number | null;
  sessions_pct?: number | null;
  utilization_pct_of_target?: number | null;
  revenue_pct?: number | null;
};

export type KpiSummary = {
  period: KpiPeriod;
  date_from: string;
  date_to: string;
  sessions_count: number;
  utilization_pct: number;
  revenue_estimate: number;
  payments_gross_minor: number;
  refunds_total_minor: number;
  net_revenue_minor: number;
  outstanding_minor: number;
  ride_breakdown: KpiRideBreakdownItem[];
  timeline: KpiTimelinePoint[];
  plan_fact?: KpiPlanFact | null;
};

export type PreflightCheckItem = {
  level: PreflightLevel;
  code: string;
  message: string;
};

export type PreflightSummary = {
  target_date: string;
  blockers: number;
  warnings: number;
  checks: PreflightCheckItem[];
};

export type SmokeCheckItem = {
  level: SmokeLevel;
  code: string;
  message: string;
};

export type SmokeSummary = {
  target_date: string;
  ok: boolean;
  created_booking_id?: string | null;
  selected_client_id?: string | null;
  selected_slot?: string | null;
  checks: SmokeCheckItem[];
};

export type PilotQueueItem = {
  booking_id: string;
  date: string;
  time: string;
  boat_id: string;
  client_id: string;
  client_name: string;
  status: BookingStatus;
  coach_required: boolean;
  ride_type?: RideType | null;
};

export type AvailabilityItem = {
  date: string;
  time: string;
  boat_id: string;
  capacity: number;
  booked: number;
  available: number;
  status: string;
};

export type BookingCreateRequest = {
  booking_id?: string;
  client_id: string;
  date: string;
  time: string;
  boat_id: string;
  coach_required?: boolean;
  coach_user_id?: string;
  ride_type?: RideType;
  wetsuit_required?: boolean;
  wetsuit_size?: WetsuitSize;
  wetsuit_gender?: WetsuitGender;
  discount?: number;
  notes?: string;
};

export type BookingCreateResponse = {
  booking_id: string;
  status: BookingStatus;
  total_price: number;
};

export type BookingItem = {
  booking_id: string;
  client_id: string;
  client_name: string;
  client_phone: string;
  date: string;
  time: string;
  boat_id: string;
  status: BookingStatus;
  coach_required: boolean;
  coach_user_id?: string | null;
  ride_type?: RideType | null;
  wetsuit_required: boolean;
  wetsuit_size?: WetsuitSize | null;
  wetsuit_gender?: WetsuitGender | null;
  total_price: number;
  payment_status: PaymentStatus;
  paid_amount_minor: number;
  refunded_amount_minor: number;
  net_paid_minor: number;
  balance_due_minor: number;
  notes: string;
};

export type PaymentMutationResponse = {
  payment: {
    payment_id: string;
    booking_id: string;
    kind: "charge" | "refund";
    status: "pending" | "succeeded" | "failed" | "cancelled";
    method: PaymentMethod;
    amount_minor: number;
    currency: string;
    paid_at?: string;
    occurred_at?: string;
    recorded_by?: string;
  };
  summary: {
    booking_id: string;
    expected_amount_minor: number;
    paid_amount_minor: number;
    refunded_amount_minor: number;
    net_paid_minor: number;
    balance_due_minor: number;
    payment_status: PaymentStatus;
  };
};

export type ClientItem = {
  client_id: string;
  full_name: string;
  phone: string;
  consent_face: boolean;
  consent_voice: boolean;
};

export type ClientCreateRequest = {
  full_name: string;
  phone: string;
  consent_face?: boolean;
  consent_voice?: boolean;
};

export type HealthStatus = {
  status: string;
};

export type BoatItem = {
  boat_id: string;
  boat_name: string;
  capacity_default: number;
  pilot_user_id?: string;
  is_active: boolean;
};

export type CheckinItem = {
  checkin_id: string;
  club_id: string;
  booking_id: string;
  client_id: string;
  method: "phone" | "manual" | "face" | "system";
  status: "arrived" | "ready" | "late" | "cancelled";
  ts: string;
  operator_user_id?: string | null;
  consent_face?: boolean;
  consent_voice?: boolean;
};

export type CheckinCreateRequest = {
  method: "phone" | "manual" | "face";
  date: string;
  phone?: string;
  client_id?: string;
  booking_id?: string;
  status?: "arrived" | "ready" | "late" | "cancelled";
};

export type LeadStatus = "new" | "contacted" | "booked" | "lost";

export type LeadItem = {
  lead_id: string;
  full_name: string;
  phone: string;
  source: string;
  status: LeadStatus;
  utm_source: string;
  utm_campaign: string;
  created_at: string;
  notes: string;
  external_source?: string;
  external_record_id?: string;
  received_at?: string;
  sync_status?: string;
  sync_error?: string;
  converted_booking_id?: string;
};

export type MarketingFunnel = {
  period_from: string;
  period_to: string;
  leads_count: number;
  contacted_count: number;
  booked_count: number;
  lost_count: number;
  conversion_to_booked_pct: number;
  cac_estimate?: number | null;
};

export type ShiftSummary = {
  total_bookings: number;
  checkins_count: number;
  confirmed: number;
  arrived: number;
  ready: number;
  in_progress: number;
  done: number;
  late: number;
  no_show: number;
  cancelled: number;
};

export type ShiftToday = {
  date: string;
  bookings: BookingItem[];
  checkins: CheckinItem[];
  summary: ShiftSummary;
};

export type ClientStats = {
  client_id: string;
  full_name: string;
  phone: string;
  consent_face: boolean;
  consent_voice: boolean;
  sessions_count: number;
  revenue_estimate: number;
  visits_count: number;
  last_visit_date: string;
};

export type PublicBookingRequest = {
  full_name: string;
  phone: string;
  date: string;
  time: string;
  ride_type?: RideType;
  notes?: string;
};

export type PublicBookingRequestResponse = {
  lead_id: string;
  status: string;
  message: string;
};

