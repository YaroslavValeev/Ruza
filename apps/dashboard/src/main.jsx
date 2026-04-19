import React, { useMemo, useState } from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import "./styles.css";

const API_BASE = import.meta.env.VITE_API_BASE || "http://localhost:8000";

function StatusBadge({ text }) {
  return <span className={`badge badge-${(text || "none").toLowerCase()}`}>{text || "—"}</span>;
}

async function apiGet(path, token) {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  const data = await res.json();
  if (!res.ok) throw new Error(`${data.code || "ERROR"}: ${data.message || "Request failed"}`);
  return data;
}

async function apiPost(path, token, body) {
  const res = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify(body),
  });
  const data = await res.json();
  if (!res.ok) throw new Error(`${data.code || "ERROR"}: ${data.message || "Request failed"}`);
  return data;
}

async function apiPatch(path, token, body) {
  const res = await fetch(`${API_BASE}${path}`, {
    method: "PATCH",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify(body),
  });
  const data = await res.json();
  if (!res.ok) throw new Error(`${data.code || "ERROR"}: ${data.message || "Request failed"}`);
  return data;
}


function toUserError(raw) {
  const txt = String(raw || "");
  if (txt.includes("SLOT_FULL")) return "Слот заполнен. Выберите другое время.";
  if (txt.includes("BOOKING_NOT_FOUND")) return "Бронирование не найдено. Обновите список дня.";
  if (txt.includes("FORBIDDEN")) return "Недостаточно прав для этого действия.";
  if (txt.includes("TAB_MISSING") || txt.includes("COLUMN_MISSING")) {
    return "Ошибка схемы таблицы. Проверьте вкладки и заголовки PRO v1.";
  }
  return txt;
}

function Shell({ title }) {
  return (
    <div className="page">
      <h1>{title}</h1>
      <p>Placeholder screen.</p>
    </div>
  );
}


function KpiView() {
  const today = new Date().toISOString().slice(0, 10);
  const [date, setDate] = useState(today);
  const [period, setPeriod] = useState("today");
  const [kpi, setKpi] = useState(null);
  const [drill, setDrill] = useState(null);
  const [message, setMessage] = useState("");
  const token = useMemo(() => localStorage.getItem("token") || "", []);

  async function loadKpi() {
    try {
      const data = await apiGet(`/kpi/${period}?today=${date}`, token);
      setKpi(data);
      setMessage("");
    } catch (err) {
      setMessage(toUserError(err.message));
    }
  }

  async function openDrill(metric) {
    try {
      const data = await apiGet(`/kpi/drilldown?period=${period}&metric=${metric}&today=${date}`, token);
      setDrill(data);
    } catch (err) {
      setMessage(toUserError(err.message));
    }
  }

  return (
    <div className="page">
      <h1>KPI Cards</h1>
      <div className="row">
        <input type="date" value={date} onChange={(e) => setDate(e.target.value)} />
        <button onClick={() => setDate(new Date().toISOString().slice(0, 10))}>Today</button>
        <button onClick={() => setDate(new Date(Date.now() + 86400000).toISOString().slice(0, 10))}>Tomorrow</button>
        <select value={period} onChange={(e) => setPeriod(e.target.value)}>
          <option value="today">today</option>
          <option value="week">week</option>
          <option value="month">month</option>
        </select>
        <button onClick={loadKpi}>Load KPI</button>
      </div>
      {kpi && (
        <div className="row wrap">
          {Object.entries(kpi.metrics).map(([key, value]) => (
            <button key={key} className="card" onClick={() => openDrill(key)}>
              <div className="k">{key}</div>
              <div className="v">{String(value)}</div>
            </button>
          ))}
        </div>
      )}
      {drill && (
        <div>
          <h2>Drilldown: {drill.metric}</h2>
          <ul>
            {drill.bookings.map((b) => (
              <li key={b.booking_id}>{b.booking_id} / {b.status} / {b.total_price || "0"}</li>
            ))}
          </ul>
        </div>
      )}
      {message && <p>{message}</p>}
    </div>
  );
}

function OperatorView() {
  const today = new Date().toISOString().slice(0, 10);
  const [date, setDate] = useState(today);
  const [boatId, setBoatId] = useState("boat_01");
  const [slots, setSlots] = useState([]);
  const [queue, setQueue] = useState([]);
  const [message, setMessage] = useState("");
  const [form, setForm] = useState({
    client_id: "client_demo",
    time: "10:00",
    boat_id: "boat_01",
    price_base: 3000,
    price_coach: 0,
    coach_required: false,
    coach_user_id: "",
  });

  const token = useMemo(() => localStorage.getItem("token") || "", []);

  async function reloadAll() {
    try {
      setMessage("");
      const [availability, pilotQueue] = await Promise.all([
        apiGet(`/availability?date=${date}`, token),
        apiGet(`/pilot/today?boat_id=${boatId}&date=${date}`, token),
      ]);
      setSlots(availability);
      setQueue(pilotQueue);
    } catch (err) {
      setMessage(toUserError(err.message));
    }
  }

  async function createBooking() {
    try {
      setMessage("");
      const created = await apiPost("/bookings", token, { ...form, date, boat_id: boatId });
      setMessage(`Booking created: ${created.booking_id}`);
      await reloadAll();
    } catch (err) {
      setMessage(toUserError(err.message));
    }
  }

  async function markCheckin(bookingId, status) {
    try {
      setMessage("");
      await apiPost("/checkins", token, {
        booking_id: bookingId,
        method: "manual",
        status,
      });
      setMessage(`Check-in ${status}: ${bookingId}`);
      await reloadAll();
    } catch (err) {
      setMessage(toUserError(err.message));
    }
  }

  return (
    <div className="page">
      <h1>Operator — Week 2/3</h1>
      <div className="row">
        <label>
          Date
          <input type="date" value={date} onChange={(e) => setDate(e.target.value)} />
        </label>
        <button onClick={() => setDate(new Date().toISOString().slice(0, 10))}>Today</button>
        <button onClick={() => setDate(new Date(Date.now() + 86400000).toISOString().slice(0, 10))}>Tomorrow</button>
        <label>
          Boat
          <input value={boatId} onChange={(e) => setBoatId(e.target.value)} />
        </label>
        <button onClick={reloadAll}>Load day</button>
      </div>

      <h2>Availability</h2>
      <table>
        <thead>
          <tr>
            <th>Time</th>
            <th>Boat</th>
            <th>Remaining</th>
            <th>Status</th>
          </tr>
        </thead>
        <tbody>
          {slots.map((slot) => (
            <tr key={`${slot.time}_${slot.boat_id}`}>
              <td>{slot.time}</td>
              <td>{slot.boat_id}</td>
              <td>{slot.remaining}</td>
              <td>
                <StatusBadge text={slot.status} />
              </td>
            </tr>
          ))}
        </tbody>
      </table>

      <h2>Create booking</h2>
      <div className="row">
        <input
          placeholder="client_id"
          value={form.client_id}
          onChange={(e) => setForm({ ...form, client_id: e.target.value })}
        />
        <input
          type="time"
          value={form.time}
          onChange={(e) => setForm({ ...form, time: e.target.value })}
        />
        <button onClick={createBooking}>Create booking</button>
      </div>

      <h2>Check-in controls</h2>
      <table>
        <thead>
          <tr>
            <th>Booking</th>
            <th>Time</th>
            <th>Status</th>
            <th>Ready</th>
            <th>Actions</th>
          </tr>
        </thead>
        <tbody>
          {queue.map((item) => (
            <tr key={item.booking_id}>
              <td>{item.booking_id}</td>
              <td>{item.time}</td>
              <td>
                <StatusBadge text={item.status} />
              </td>
              <td>
                <StatusBadge text={item.ready_state} />
              </td>
              <td>
                <button onClick={() => markCheckin(item.booking_id, "arrived")}>Arrived</button>
                <button onClick={() => markCheckin(item.booking_id, "ready")}>Ready</button>
                <button onClick={() => markCheckin(item.booking_id, "late")}>Late</button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      {message && <p>{message}</p>}
    </div>
  );
}

function PilotView() {
  const today = new Date().toISOString().slice(0, 10);
  const [date, setDate] = useState(today);
  const [boatId, setBoatId] = useState("boat_01");
  const [queue, setQueue] = useState([]);
  const [message, setMessage] = useState("");
  const token = useMemo(() => localStorage.getItem("token") || "", []);

  async function loadQueue() {
    try {
      setMessage("");
      const data = await apiGet(`/pilot/today?boat_id=${boatId}&date=${date}`, token);
      setQueue(data);
    } catch (err) {
      setMessage(toUserError(err.message));
    }
  }

  async function patchStatus(bookingId, status) {
    try {
      await apiPatch(`/bookings/${bookingId}`, token, { status });
      setMessage(`${bookingId} -> ${status}`);
      await loadQueue();
    } catch (err) {
      setMessage(toUserError(err.message));
    }
  }

  return (
    <div className="page">
      <h1>Pilot Queue</h1>
      <div className="row">
        <input type="date" value={date} onChange={(e) => setDate(e.target.value)} />
        <button onClick={() => setDate(new Date().toISOString().slice(0, 10))}>Today</button>
        <button onClick={() => setDate(new Date(Date.now() + 86400000).toISOString().slice(0, 10))}>Tomorrow</button>
        <input value={boatId} onChange={(e) => setBoatId(e.target.value)} />
        <button onClick={loadQueue}>Load queue</button>
      </div>

      <table>
        <thead>
          <tr>
            <th>Time</th>
            <th>Client</th>
            <th>Status</th>
            <th>Ready</th>
            <th>Actions</th>
          </tr>
        </thead>
        <tbody>
          {queue.map((item) => (
            <tr key={item.booking_id}>
              <td>{item.time}</td>
              <td>{item.client}</td>
              <td>
                <StatusBadge text={item.status} />
              </td>
              <td>
                <StatusBadge text={item.ready_state} />
              </td>
              <td>
                <button onClick={() => patchStatus(item.booking_id, "in_progress")}>Start</button>
                <button onClick={() => patchStatus(item.booking_id, "done")}>Done</button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      {message && <p>{message}</p>}
    </div>
  );
}

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Navigate to="/operator" replace />} />
        <Route path="/kpi" element={<KpiView />} />
        <Route path="/operator" element={<OperatorView />} />
        <Route path="/pilot" element={<PilotView />} />
      </Routes>
    </BrowserRouter>
  );
}

ReactDOM.createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
