
import { useCallback, useEffect, useState } from "react";
import ReactMarkdown from "react-markdown";
import {
  Activity,
  ArrowDownRight,
  ArrowUpRight,
  Bell,
  ChevronDown,
  CircleHelp,
  LayoutDashboard,
  RefreshCw,
  ShieldCheck,
  Wallet,
  TrendingDown,
  AlertTriangle,
  CalendarDays,
  Sparkles,
  SlidersHorizontal,
  Play,
  RotateCcw,
} from "lucide-react";
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import "./App.css";

const API = "http://127.0.0.1:8000";
const PAGE_IDS = ["overview", "cash-flow", "risk-analysis", "transactions", "help-methodology"];

const money = (value) =>
  new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: 0,
  }).format(Number.isFinite(Number(value)) ? Number(value) : 0);

const percentage = (value, digits = 2) =>
  Number.isFinite(Number(value))
    ? `${(Number(value) * 100).toFixed(digits)}%`
    : "—";

function App() {
  const [account, setAccount] = useState(null);
  const [businessHistory, setBusinessHistory] = useState(null);
  const [businessHistoryError, setBusinessHistoryError] = useState("");
  const [forecast, setForecast] = useState([]);
  const [risk, setRisk] = useState(null);
  const [mlRisk, setMlRisk] = useState(null);
  const [paymentTiming, setPaymentTiming] = useState(null);
  const [paymentTimingLoading, setPaymentTimingLoading] = useState(true);
  const [paymentTimingError, setPaymentTimingError] = useState("");
  const [decisionData, setDecisionData] = useState(null);
  const [decisionError, setDecisionError] = useState("");
  const [riskDrivers, setRiskDrivers] = useState(null);
  const [stressTests, setStressTests] = useState(null);
  const [quantError, setQuantError] = useState("");
  const [connected, setConnected] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [briefing, setBriefing] = useState("");
  const [briefingLoading, setBriefingLoading] = useState(false);
  const [briefingError, setBriefingError] = useState("");
  const [whatIfInputs, setWhatIfInputs] = useState({
    payroll_amount: 7000,
    deposit_amount: 3000,
    deposit_delay_days: 0,
    safety_buffer: 5000,
  });
  const [whatIfLoading, setWhatIfLoading] = useState(false);
  const [whatIfError, setWhatIfError] = useState("");
  const [whatIfResult, setWhatIfResult] = useState(null);
  const [activePage, setActivePage] = useState(() => {
    const requestedPage = window.location.hash.slice(1);
    return PAGE_IDS.includes(requestedPage) ? requestedPage : "overview";
  });

  useEffect(() => {
    const syncPageFromUrl = () => {
      const requestedPage = window.location.hash.slice(1);
      setActivePage(PAGE_IDS.includes(requestedPage) ? requestedPage : "overview");
    };
    window.addEventListener("popstate", syncPageFromUrl);
    window.addEventListener("hashchange", syncPageFromUrl);
    return () => {
      window.removeEventListener("popstate", syncPageFromUrl);
      window.removeEventListener("hashchange", syncPageFromUrl);
    };
  }, []);

  const navigateToPage = (page) => {
    if (!PAGE_IDS.includes(page)) return;
    window.history.pushState({ page }, "", `#${page}`);
    setActivePage(page);
    window.scrollTo({ top: 0, behavior: "smooth" });
  };

  const loadDashboard = useCallback(async () => {
    setLoading(true);
    setError("");

    try {
      const [
        healthRes,
        accountRes,
        forecastRes,
        riskRes,
        mlRiskRes,
      ] = await Promise.all([
        fetch(`${API}/api/health`),
        fetch(`${API}/api/account`),
        fetch(`${API}/api/forecast`),
        fetch(`${API}/api/risk`),
        fetch(`${API}/api/ml-risk`),
      ]);

      const responses = [
        healthRes,
        accountRes,
        forecastRes,
        riskRes,
        mlRiskRes,
      ];

      const failedResponse = responses.find((response) => !response.ok);

      if (failedResponse) {
        throw new Error(
          `Backend request failed with HTTP ${failedResponse.status}.`
        );
      }

      const [
        healthData,
        accountData,
        forecastData,
        riskData,
        mlRiskData,
      ] = await Promise.all(
        responses.map((response) => response.json())
      );

      if (healthData.status !== "ok") {
        throw new Error("The backend health check failed.");
      }

      const accountBalance = Number(accountData.balance);

      if (!Number.isFinite(accountBalance)) {
        throw new Error("The account endpoint returned an invalid balance.");
      }

      const forecastRows = forecastData.forecast;

      if (!Array.isArray(forecastRows)) {
        throw new Error("The forecast endpoint returned invalid data.");
      }

      const normalizedForecast = forecastRows.map((item) => ({
        ...item,
        date: item.date
          ? item.date.slice(5)
          : "Unknown",
        projected_balance: Number(item.projected_balance),
      }));

      setAccount(accountData);
      setForecast(normalizedForecast);
      setRisk(riskData.monte_carlo ?? null);
      setMlRisk(mlRiskData);
      setConnected(true);
    } catch (err) {
      setConnected(false);
      setError(
        err.message ||
          "Unable to load data. Check that the FastAPI backend is running."
      );
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      void loadDashboard();
    }, 0);

    return () => window.clearTimeout(timer);
  }, [loadDashboard]);

  useEffect(() => {
    let cancelled = false;

    async function loadPaymentTiming() {
      setPaymentTimingLoading(true);
      setPaymentTimingError("");

      try {
        const response = await fetch(`${API}/api/payment-timing`);

        if (!response.ok) {
          throw new Error(
            `Payment-timing request failed (HTTP ${response.status}).`
          );
        }

        const data = await response.json();

        if (!cancelled) {
          setPaymentTiming(data);
        }
      } catch (err) {
        if (!cancelled) {
          setPaymentTimingError(
            err.message || "Unable to load payment-timing status."
          );
        }
      } finally {
        if (!cancelled) {
          setPaymentTimingLoading(false);
        }
      }
    }

    loadPaymentTiming();

    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    let cancelled = false;
    fetch(`${API}/api/demo-business-history`)
      .then(async (response) => {
        const data = await response.json();
        if (!response.ok) throw new Error(data.detail || "Demo history unavailable.");
        return data;
      })
      .then((data) => { if (!cancelled) setBusinessHistory(data); })
      .catch((err) => { if (!cancelled) setBusinessHistoryError(err.message); });
    return () => { cancelled = true; };
  }, []);

  useEffect(() => {
    let cancelled = false;
    Promise.all([
      fetch(`${API}/api/risk-attribution?simulations=2000`).then(async (r) => {
        const d = await r.json(); if (!r.ok) throw new Error(d.detail || "Risk drivers unavailable"); return d.risk_attribution;
      }),
      fetch(`${API}/api/stress-test?simulations=2000`).then(async (r) => {
        const d = await r.json(); if (!r.ok) throw new Error(d.detail || "Stress tests unavailable"); return d.stress_tests;
      }),
    ]).then(([drivers, tests]) => {
      if (!cancelled) { setRiskDrivers(drivers); setStressTests(tests); }
    }).catch((err) => { if (!cancelled) setQuantError(err.message); });
    return () => { cancelled = true; };
  }, []);

  useEffect(() => {
    let cancelled = false;
    fetch(`${API}/api/decision`)
      .then(async (response) => {
        const data = await response.json();
        if (!response.ok) throw new Error(data.detail || "Intervention analysis unavailable.");
        return data.decision;
      })
      .then((data) => { if (!cancelled) setDecisionData(data); })
      .catch((err) => { if (!cancelled) setDecisionError(err.message); });
    return () => { cancelled = true; };
  }, []);

  const loadBriefing = useCallback(async () => {
    setBriefingLoading(true);
    setBriefingError("");

    try {
      const response = await fetch(`${API}/api/briefing`);
      const data = await response.json();

      if (!response.ok) {
        throw new Error(
          data.detail || "Unable to generate financial briefing."
        );
      }

      setBriefing(data.briefing || "");
    } catch (err) {
      setBriefingError(
        err.message || "Gemini briefing is unavailable."
      );
    } finally {
      setBriefingLoading(false);
    }
  }, []);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      void loadBriefing();
    }, 0);

    return () => window.clearTimeout(timer);
  }, [loadBriefing]);

  const updateWhatIfInput = (field, value) => {
    setWhatIfInputs((current) => ({ ...current, [field]: value }));
  };

  const runWhatIf = async (event) => {
    event.preventDefault();
    setWhatIfLoading(true);
    setWhatIfError("");

    try {
      const response = await fetch(`${API}/api/what-if`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          payroll_amount: Number(whatIfInputs.payroll_amount),
          deposit_amount: Number(whatIfInputs.deposit_amount),
          deposit_delay_days: Number(whatIfInputs.deposit_delay_days),
          safety_buffer: Number(whatIfInputs.safety_buffer),
        }),
      });

      const data = await response.json();
      if (!response.ok) {
        throw new Error(
          data.detail || "Unable to run this scenario."
        );
      }
      setWhatIfResult(data);
    } catch (err) {
      setWhatIfError(
        err.message ||
          "What-if simulation failed. Check that the backend endpoint is installed."
      );
    } finally {
      setWhatIfLoading(false);
    }
  };

  const resetWhatIf = () => {
    setWhatIfInputs({
      payroll_amount: 7000,
      deposit_amount: 3000,
      deposit_delay_days: 0,
      safety_buffer: 5000,
    });
    setWhatIfResult(null);
    setWhatIfError("");
  };

  const endingBalance =
    forecast.length > 0
      ? forecast[forecast.length - 1].projected_balance
      : null;

  const accountName = account?.nickname || "Nesshield Account";

  const forecastStart =
    forecast.length > 0 ? forecast[0].date : "—";

  const forecastEnd =
    forecast.length > 0
      ? forecast[forecast.length - 1].date
      : "—";

  const safetyBufferProbability = risk?.safety_buffer_breach_probability;
  const shortfallProbability = risk?.shortfall_probability;

  const bufferRiskValue = Number(safetyBufferProbability);
  const ringDegrees = Number.isFinite(bufferRiskValue)
    ? Math.min(100, Math.max(0, bufferRiskValue * 100))
    : 0;
  const scheduledInflows = forecast.reduce((sum, row) => sum + Number(row.scheduled_inflows || 0), 0);
  const scheduledOutflows = forecast.reduce((sum, row) => sum + Number(row.scheduled_outflows || 0), 0);
  const lowestForecastBalance = forecast.length
    ? Math.min(...forecast.map((row) => Number(row.projected_balance)))
    : null;
  const forecastFlowRows = forecast.map((row) => ({
    ...row,
    net_activity: Number(row.scheduled_inflows || 0) - Number(row.scheduled_outflows || 0),
  }));
  const riskFanRows = Object.entries(risk?.daily_balance_percentiles || {}).map(([day, values]) => ({
    day: `Day ${day}`,
    ...values,
  }));
  const breachRows = Object.entries(risk?.probability_of_breach_by_day || {}).map(([day, probability]) => ({
    day: `Day ${day}`,
    probability: Number(probability),
  }));
  const stressRows = Object.entries(stressTests?.scenarios || {}).map(([name, result]) => ({
    name: name.replaceAll("_", " "),
    probability: Number(result.metrics?.safety_buffer_breach_probability || 0),
  }));
  const actionRows = (decisionData?.comparisons || []).map((item) => ({
    name: item.name,
    risk: Number(item.safety_buffer_breach_probability || 0),
    cost: Number(item.cost || 0),
  }));
  const historicalMonths = businessHistory?.months || [];
  const historicalRows = historicalMonths.map((row) => ({
    ...row,
    period: new Date(`${row.month}-01T00:00:00`).toLocaleDateString("en-US", { month: "short", year: "2-digit" }),
    margin: row.revenue > 0 ? row.net_cash_flow / row.revenue : 0,
  }));
  const recentHistoricalTransactions = [...(businessHistory?.transactions || [])].slice(-16).reverse();
  const latestTwelveMonths = historicalMonths.slice(-12);
  const trailingRevenue = latestTwelveMonths.reduce((sum, row) => sum + Number(row.revenue || 0), 0);
  const trailingExpenses = latestTwelveMonths.reduce((sum, row) => sum + Number(row.expenses || 0), 0);
  const pageCopy = {
    overview: ["BUSINESS OVERVIEW / CASH POSITION", "Good afternoon", "Live sandbox liquidity with a 24-month illustrative small-business operating profile."],
    "cash-flow": ["CASH FLOW / FORECAST", "Cash flow", "Compare the daily Nessie ledger forecast with two years of seasonal business cash movement."],
    "risk-analysis": ["RISK ANALYSIS / LIQUIDITY", "Risk analysis", "Explore modeled downside, stress cases, and historical demo-business volatility."],
    transactions: ["WORKSPACE / TRANSACTIONS", "Transactions", "Upcoming sandbox entries plus a detailed synthetic two-year small-business ledger."],
    "help-methodology": ["REFERENCE / METHODOLOGY", "Help & methodology", "Data provenance, model assumptions, and limits behind NesShield's estimates."],
  }[activePage];

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-mark">
            <ShieldCheck size={25} />
          </div>

          <div>
            <div className="brand-name">
              NesShield<span> AI</span>
            </div>
            <div className="brand-subtitle">
              FINANCIAL INTELLIGENCE
            </div>
          </div>
        </div>

        <div className="nav-label">WORKSPACE</div>

        <nav className="section-nav" aria-label="Dashboard sections">
          <button type="button" className={`nav-item ${activePage === "overview" ? "active" : ""}`} aria-current={activePage === "overview" ? "page" : undefined} onClick={() => navigateToPage("overview")}>
            <LayoutDashboard size={18} />
            Overview
          </button>
          <button type="button" className={`nav-item ${activePage === "cash-flow" ? "active" : ""}`} aria-current={activePage === "cash-flow" ? "page" : undefined} onClick={() => navigateToPage("cash-flow")}>
            <Activity size={18} />
            Cash flow
          </button>
          <button type="button" className={`nav-item ${activePage === "risk-analysis" ? "active" : ""}`} aria-current={activePage === "risk-analysis" ? "page" : undefined} onClick={() => navigateToPage("risk-analysis")}>
            <TrendingDown size={18} />
            Risk analysis
          </button>
          <button type="button" className={`nav-item ${activePage === "transactions" ? "active" : ""}`} aria-current={activePage === "transactions" ? "page" : undefined} onClick={() => navigateToPage("transactions")}>
            <Wallet size={18} />
            Transactions
          </button>
          <button type="button" className={`nav-item ${activePage === "help-methodology" ? "active" : ""}`} aria-current={activePage === "help-methodology" ? "page" : undefined} onClick={() => navigateToPage("help-methodology")}>
            <CircleHelp size={18} />
            Help &amp; methodology
          </button>
        </nav>

        <div className="sidebar-bottom">
          <div className="sidebar-status">
            <span
              className={`status-dot ${connected ? "online" : ""}`}
            />
            <div>
              <div className="status-title">
                {connected
                  ? "Sandbox connected"
                  : loading
                    ? "Connecting…"
                    : "Connection unavailable"}
              </div>
              <div className="status-caption">Nessie API</div>
            </div>
          </div>

        </div>
      </aside>

      <main className="main-content">
        <header className="topbar">
          <div>
            <div className="eyebrow">{pageCopy[0]}</div>
            <h1>{pageCopy[1]}{activePage === "overview" && <span className="wave"> ✳</span>}</h1>
            <p className="page-subtitle">{pageCopy[2]}</p>
          </div>

          <div className="top-actions">
            <button
              className="icon-button"
              aria-label="Refresh dashboard"
              onClick={loadDashboard}
              disabled={loading}
            >
              <Bell size={18} />
            </button>

            <button className="profile-button">
              <div className="avatar">NS</div>
              <div className="profile-text">
                <strong>{accountName}</strong>
                <small>Demo account · Nessie sandbox</small>
              </div>
              <ChevronDown size={16} />
            </button>
          </div>
        </header>

        {error && (
          <div className="error-banner">
            <AlertTriangle size={17} />
            <span>
              Unable to refresh live data: {error}
            </span>
            <button
              className="text-button"
              onClick={loadDashboard}
              disabled={loading}
            >
              Retry
            </button>
          </div>
        )}

        {activePage === "overview" && (
          <>
        <section className="hero-card page-anchor" id="overview">
          <div className="hero-copy">
            <div className="hero-label">
              <span className="live-dot" />
              CASH POSITION
            </div>

            <div className="hero-balance">
              {account ? money(account.balance) : "—"}
            </div>

            <p>
              Current account balance{" "}
              <span className="hero-tag">
                {connected ? "Nessie sandbox · Live" : "Not connected"}
              </span>
            </p>

            <div className="hero-divider" />

            <div className="hero-foot">
              <span>
                <Activity size={15} />
                7-day forecast
              </span>
              <span>
                <CalendarDays size={15} />
                {forecastStart} – {forecastEnd}
              </span>
            </div>
          </div>

          <div className="hero-art">
            <div className="orbit orbit-one" />
            <div className="orbit orbit-two" />
            <div className="hero-shield">
              <ShieldCheck size={66} strokeWidth={1.3} />
            </div>
            <div className="float-card">
              <span className="float-dot" />
              {connected ? "Forecast active" : "Awaiting connection"}
            </div>
          </div>
        </section>

        <section className="metric-grid">
          <article className="metric-card">
            <div className="metric-top">
              <span>Projected ending balance</span>
              <div className="metric-icon green">
                <Wallet size={18} />
              </div>
            </div>

            <div className="metric-value">
              {endingBalance !== null ? money(endingBalance) : "—"}
            </div>

            <div className="metric-foot">
              <ArrowDownRight size={15} />
              After scheduled transactions
            </div>
          </article>

          <article className="metric-card">
            <div className="metric-top">
              <span>Safety-buffer breach</span>
              <div className="metric-icon amber">
                <AlertTriangle size={18} />
              </div>
            </div>

            <div className="metric-value">
              {percentage(safetyBufferProbability)}
            </div>

            <div className="metric-foot muted">
              Estimated · $5,000 buffer
            </div>
          </article>

          <article className="metric-card">
            <div className="metric-top">
              <span>Shortfall probability</span>
              <div className="metric-icon blue">
                <Activity size={18} />
              </div>
            </div>

            <div className="metric-value">
              {percentage(shortfallProbability)}
            </div>

            <div className="metric-foot muted">
              Monte Carlo scenarios
            </div>
          </article>

          <article className="metric-card">
            <div className="metric-top">
              <span>Downside estimate · P05</span>
              <div className="metric-icon purple">
                <TrendingDown size={18} />
              </div>
            </div>

            <div className="metric-value">
              {risk ? money(risk.ending_balance_p05) : "—"}
            </div>

            <div className="metric-foot muted">
              5th percentile ending balance
            </div>
          </article>
        </section>

        <section className="content-grid page-view overview-detail-grid">
          <article className="panel">
            <div className="panel-header"><div><h2>Operating cash trajectory</h2><p>Scheduled cash movements and conservative baseline balance · {forecast.length ? `${forecast.length - 1}-day view` : "waiting for data"}</p></div><div className="metric-icon green"><Activity size={18} /></div></div>
            <div className="chart-area">
              {forecast.length ? <ResponsiveContainer width="100%" height="100%"><AreaChart data={forecast}><CartesianGrid stroke="#263940" strokeDasharray="3 3" /><XAxis dataKey="date" stroke="#81959c" tick={{ fontSize: 10 }} /><YAxis stroke="#81959c" tick={{ fontSize: 10 }} tickFormatter={(value) => `$${Math.round(value / 1000)}k`} /><Tooltip formatter={(value) => money(value)} /><Area type="monotone" dataKey="projected_balance" stroke="#42d6a0" fill="#42d6a0" fillOpacity={0.12} name="Baseline balance" /></AreaChart></ResponsiveContainer> : <p className="chart-note">{loading ? "Loading operating data…" : "No forecast available."}</p>}
            </div>
          </article>
          <article className="panel">
            <div className="panel-header"><div><h2>Cash movement profile</h2><p>Scheduled inflow and outflow by day</p></div><div className="metric-icon blue"><Wallet size={18} /></div></div>
            <div className="chart-area"><ResponsiveContainer width="100%" height="100%"><BarChart data={forecastFlowRows}><CartesianGrid stroke="#263940" strokeDasharray="3 3" /><XAxis dataKey="date" stroke="#81959c" tick={{ fontSize: 10 }} /><YAxis stroke="#81959c" tick={{ fontSize: 10 }} tickFormatter={(value) => `$${Math.round(value / 1000)}k`} /><Tooltip formatter={(value) => money(value)} /><Legend /><Bar dataKey="scheduled_inflows" name="Scheduled receipts" fill="#42d6a0" radius={[4, 4, 0, 0]} /><Bar dataKey="scheduled_outflows" name="Scheduled obligations" fill="#e6a65c" radius={[4, 4, 0, 0]} /></BarChart></ResponsiveContainer></div>
            <div className="assumption-note"><Activity size={15} /><span>Horizon receipts are pending/scheduled amounts from the ledger. The baseline does not credit pending receipts before settlement.</span></div>
          </article>
        </section>
        <section className="metric-grid operational-metrics">
          <article className="metric-card"><div className="metric-top"><span>Scheduled receipts</span></div><div className="metric-value">{money(scheduledInflows)}</div><div className="metric-foot muted">Across the displayed forecast window</div></article>
          <article className="metric-card"><div className="metric-top"><span>Scheduled obligations</span></div><div className="metric-value">{money(scheduledOutflows)}</div><div className="metric-foot muted">Pending and scheduled outflows</div></article>
          <article className="metric-card"><div className="metric-top"><span>Net scheduled movement</span></div><div className="metric-value">{money(scheduledInflows - scheduledOutflows)}</div><div className="metric-foot muted">Receipts less obligations</div></article>
          <article className="metric-card"><div className="metric-top"><span>Lowest baseline balance</span></div><div className="metric-value">{lowestForecastBalance == null ? "—" : money(lowestForecastBalance)}</div><div className="metric-foot muted">Conservative scheduled-cash path</div></article>
        </section>
        <section className="metric-grid operational-metrics">
          <article className="metric-card"><div className="metric-top"><span>Demo business · 24-month revenue</span></div><div className="metric-value">{businessHistory ? money(historicalMonths.reduce((sum, row) => sum + Number(row.revenue || 0), 0)) : "—"}</div><div className="metric-foot muted">Synthetic company operating history</div></article>
          <article className="metric-card"><div className="metric-top"><span>Trailing 12-month revenue</span></div><div className="metric-value">{businessHistory ? money(trailingRevenue) : "—"}</div><div className="metric-foot muted">Latest rolling year in demo profile</div></article>
          <article className="metric-card"><div className="metric-top"><span>Trailing 12-month expenses</span></div><div className="metric-value">{businessHistory ? money(trailingExpenses) : "—"}</div><div className="metric-foot muted">Payroll, suppliers, overhead and shocks</div></article>
          <article className="metric-card"><div className="metric-top"><span>History coverage</span></div><div className="metric-value">{businessHistory ? `${historicalMonths.length} months` : "—"}</div><div className="metric-foot muted">{businessHistory?.summary?.transaction_count?.toLocaleString() || "—"} generated transactions</div></article>
        </section>
        <section className="panel payment-timing-panel">
          <div className="panel-header"><div><h2>{businessHistory?.business_name || "Small-business operating history"}</h2><p>24-month seasonal revenue and expense profile · synthetic demo dataset</p></div><div className="metric-icon green"><Activity size={18} /></div></div>
          {historicalRows.length ? <div className="chart-area"><ResponsiveContainer width="100%" height="100%"><AreaChart data={historicalRows}><CartesianGrid stroke="#263940" strokeDasharray="3 3" /><XAxis dataKey="period" stroke="#81959c" tick={{ fontSize: 9 }} interval={2} /><YAxis stroke="#81959c" tick={{ fontSize: 10 }} tickFormatter={(value) => `$${Math.round(value / 1000)}k`} /><Tooltip labelFormatter={(value) => `Month ${value}`} formatter={(value) => money(value)} /><Legend /><Area type="monotone" dataKey="revenue" name="Customer receipts" stroke="#42d6a0" fill="#42d6a0" fillOpacity={0.08} /><Area type="monotone" dataKey="expenses" name="Operating spend" stroke="#e6a65c" fill="#e6a65c" fillOpacity={0.04} /></AreaChart></ResponsiveContainer></div> : <p className="payment-timing-message">{businessHistoryError || "Loading two-year demo history…"}</p>}
          <div className="assumption-note"><AlertTriangle size={15} /><span>{businessHistory?.disclosure || "Illustrative synthetic records, separate from Nessie live account data."}</span></div>
        </section>
          </>
        )}

        {(activePage === "cash-flow" || activePage === "risk-analysis") && (
        <section className="content-grid page-view">
          {activePage === "cash-flow" && (
          <article className="panel forecast-panel">
            <div className="panel-header">
              <div>
                <h2>Cash flow forecast</h2>
                <p>Projected balance over the next 7 days</p>
              </div>

              <button className="period-chip">
                7 days <ChevronDown size={14} />
              </button>
            </div>

            <div className="chart-legend">
              <span className="legend-dot" />
              Projected balance
            </div>

            <div className="chart-area">
              {forecast.length > 0 ? (
                <ResponsiveContainer width="100%" height="100%">
                  <AreaChart
                    data={forecast}
                    margin={{
                      top: 12,
                      right: 12,
                      left: 0,
                      bottom: 0,
                    }}
                  >
                    <defs>
                      <linearGradient
                        id="balanceFill"
                        x1="0"
                        y1="0"
                        x2="0"
                        y2="1"
                      >
                        <stop
                          offset="0%"
                          stopColor="#42d6a0"
                          stopOpacity={0.22}
                        />
                        <stop
                          offset="95%"
                          stopColor="#42d6a0"
                          stopOpacity={0.01}
                        />
                      </linearGradient>
                    </defs>

                    <CartesianGrid
                      stroke="#25333b"
                      strokeDasharray="4 5"
                      vertical={false}
                    />

                    <XAxis
                      dataKey="date"
                      stroke="#75868d"
                      tickLine={false}
                      axisLine={false}
                    />

                    <YAxis
                      stroke="#75868d"
                      tickLine={false}
                      axisLine={false}
                      width={62}
                      tickFormatter={(value) =>
                        `$${value / 1000}k`
                      }
                    />

                    <Tooltip
                      contentStyle={{
                        background: "#111d23",
                        border: "1px solid #2d4249",
                        borderRadius: 10,
                      }}
                      formatter={(value) => [
                        money(value),
                        "Projected balance",
                      ]}
                    />

                    <Area
                      type="monotone"
                      dataKey="projected_balance"
                      stroke="#42d6a0"
                      strokeWidth={2.5}
                      fill="url(#balanceFill)"
                    />
                  </AreaChart>
                </ResponsiveContainer>
              ) : (
                <div className="chart-note">
                  {loading
                    ? "Loading forecast…"
                    : "No forecast data is currently available."}
                </div>
              )}
            </div>

            <div className="chart-note">
              <span className="note-dot" />
              Baseline excludes pending deposits until they clear.
            </div>
          </article>
          )}

          {activePage === "risk-analysis" && (
          <article className="panel risk-panel">
            <div className="panel-header">
              <div>
                <h2>Risk outlook</h2>
                <p>Monte Carlo scenario analysis</p>
              </div>

              <div className="risk-icon">
                <ShieldCheck size={20} />
              </div>
            </div>

            <div className="risk-score">
              <div
                className="risk-ring"
                style={{
                  background: `conic-gradient(#d8a452 0 ${ringDegrees}%, #263b3e ${ringDegrees}% 100%)`,
                }}
              >
                <div>
                  <strong>
                    {percentage(safetyBufferProbability, 0)}
                  </strong>
                  <small>BUFFER RISK</small>
                </div>
              </div>

              <div className="risk-summary">
                <strong>
                  {risk
                    ? bufferRiskValue >= 0.5
                      ? "Elevated liquidity risk"
                      : bufferRiskValue >= 0.2
                        ? "Liquidity watch"
                        : "Lower modeled buffer risk"
                    : "Risk assessment unavailable"}
                </strong>
                <span>
                  {risk
                    ? `${(risk.simulations ?? 0).toLocaleString()} simulated scenarios`
                    : "Waiting for scenario results"}
                </span>
                <span>
                  {risk?.horizon_days ?? 7}-day horizon
                </span>
              </div>
            </div>

            <div className="risk-divider" />

            <div className="risk-stat">
              <span>Median ending balance</span>
              <strong>
                {risk ? money(risk.ending_balance_median) : "—"}
              </strong>
            </div>

            <div className="risk-stat">
              <span>Favorable case · P95</span>
              <strong>
                {risk ? money(risk.ending_balance_p95) : "—"}
              </strong>
            </div>

            <div className="risk-stat">
              <span>Safety buffer</span>
              <strong>
                {risk?.assumptions?.safety_buffer != null
                  ? money(risk.assumptions.safety_buffer)
                  : "$5,000"}
              </strong>
            </div>

            <div className="assumption-note">
              <Sparkles size={15} />
              <span>
                Scenario estimates depend on explicit assumptions.
                They are not calibrated real-world probabilities of
                business failure.
              </span>
            </div>
          </article>
          )}
        </section>
        )}

        {activePage === "cash-flow" && (
          <>
            <section className="metric-grid operational-metrics">
              <article className="metric-card"><div className="metric-top"><span>Projected trough</span></div><div className="metric-value">{lowestForecastBalance == null ? "—" : money(lowestForecastBalance)}</div><div className="metric-foot muted">Lowest point on baseline path</div></article>
              <article className="metric-card"><div className="metric-top"><span>Receipts in horizon</span></div><div className="metric-value">{money(scheduledInflows)}</div><div className="metric-foot muted">Pending ledger receipts shown separately</div></article>
              <article className="metric-card"><div className="metric-top"><span>Obligations in horizon</span></div><div className="metric-value">{money(scheduledOutflows)}</div><div className="metric-foot muted">Scheduled and pending outflows</div></article>
              <article className="metric-card"><div className="metric-top"><span>Forecast step count</span></div><div className="metric-value">{forecast.length || "—"}</div><div className="metric-foot muted">Daily ledger snapshots including today</div></article>
            </section>
            <section className="panel payment-timing-panel">
              <div className="panel-header"><div><h2>Daily cash movement</h2><p>Receipts and obligations by ledger date</p></div><div className="metric-icon blue"><Activity size={18} /></div></div>
              {forecast.length ? <div className="chart-area"><ResponsiveContainer width="100%" height="100%"><BarChart data={forecastFlowRows}><CartesianGrid stroke="#263940" strokeDasharray="3 3" /><XAxis dataKey="date" stroke="#81959c" tick={{ fontSize: 10 }} /><YAxis stroke="#81959c" tick={{ fontSize: 10 }} tickFormatter={(value) => `$${Math.round(value / 1000)}k`} /><Tooltip formatter={(value) => money(value)} /><Legend /><Bar dataKey="scheduled_inflows" name="Receipts" fill="#42d6a0" radius={[4, 4, 0, 0]} /><Bar dataKey="scheduled_outflows" name="Obligations" fill="#e6a65c" radius={[4, 4, 0, 0]} /></BarChart></ResponsiveContainer></div> : <p className="payment-timing-message">{loading ? "Loading ledger activity…" : "No dated ledger activity is available."}</p>}
              <div className="assumption-note"><AlertTriangle size={15} /><span>The deterministic baseline subtracts pending/scheduled outflows and does not credit pending receipts until settlement. Scenario uncertainty is shown separately on Risk analysis.</span></div>
            </section>
            <section className="panel payment-timing-panel">
              <div className="panel-header"><div><h2>Two-year operating trend</h2><p>{businessHistory?.business_name || "Fictional service business"} · monthly receipts, expenses and net cash flow</p></div><div className="metric-icon purple"><TrendingDown size={18} /></div></div>
              {historicalRows.length ? <div className="chart-area"><ResponsiveContainer width="100%" height="100%"><LineChart data={historicalRows}><CartesianGrid stroke="#263940" strokeDasharray="3 3" /><XAxis dataKey="period" stroke="#81959c" tick={{ fontSize: 9 }} interval={2} /><YAxis stroke="#81959c" tick={{ fontSize: 10 }} tickFormatter={(value) => `$${Math.round(value / 1000)}k`} /><Tooltip formatter={(value) => money(value)} /><Legend /><Line type="monotone" dataKey="revenue" stroke="#42d6a0" dot={false} name="Revenue" /><Line type="monotone" dataKey="expenses" stroke="#e6a65c" dot={false} name="Operating expenses" /><Line type="monotone" dataKey="net_cash_flow" stroke="#79b9f3" dot={false} name="Net cash flow" /></LineChart></ResponsiveContainer></div> : <p className="payment-timing-message">{businessHistoryError || "Loading historical operating trend…"}</p>}
              <div className="assumption-note"><Sparkles size={15} /><span>Seasonality, invoice settlement delays, supplier variability, and occasional repair/tax shocks make the history intentionally uneven. This synthetic history is contextual demo data; the live Nessie forecast remains a separate account feed.</span></div>
            </section>
          </>
        )}

        {activePage === "risk-analysis" && (
          <section className="content-grid page-view risk-detail-grid">
            <article className="panel">
              <div className="panel-header"><div><h2>Liquidity fan chart</h2><p>Monte Carlo balance percentiles by day · {risk?.simulations?.toLocaleString() || "—"} paths</p></div><div className="metric-icon purple"><TrendingDown size={18} /></div></div>
              {riskFanRows.length ? <div className="chart-area"><ResponsiveContainer width="100%" height="100%"><AreaChart data={riskFanRows}><CartesianGrid stroke="#263940" strokeDasharray="3 3" /><XAxis dataKey="day" stroke="#81959c" tick={{ fontSize: 10 }} /><YAxis stroke="#81959c" tick={{ fontSize: 10 }} tickFormatter={(value) => `$${Math.round(value / 1000)}k`} /><Tooltip formatter={(value) => money(value)} /><Area type="monotone" dataKey="p95" stroke="#42d6a0" fill="#42d6a0" fillOpacity={0.07} name="P95 favorable" /><Line type="monotone" dataKey="p50" stroke="#79b9f3" dot={false} name="P50 median" /><Line type="monotone" dataKey="p05" stroke="#e6a65c" dot={false} name="P05 downside" /></AreaChart></ResponsiveContainer></div> : <p className="payment-timing-message">Waiting for percentile paths from Monte Carlo.</p>}
              <div className="assumption-note"><Sparkles size={15} /><span>Percentiles summarize simulated scenarios under configured assumptions; they are not confidence bounds calibrated to observed business outcomes.</span></div>
            </article>
            <article className="panel">
              <div className="panel-header"><div><h2>Buffer-breach trajectory</h2><p>Modeled cumulative chance of crossing the reserve threshold</p></div><div className="metric-icon amber"><AlertTriangle size={18} /></div></div>
              {breachRows.length ? <div className="chart-area"><ResponsiveContainer width="100%" height="100%"><LineChart data={breachRows}><CartesianGrid stroke="#263940" strokeDasharray="3 3" /><XAxis dataKey="day" stroke="#81959c" tick={{ fontSize: 10 }} /><YAxis domain={[0, 1]} stroke="#81959c" tickFormatter={(value) => `${Math.round(value * 100)}%`} /><Tooltip formatter={(value) => percentage(value)} /><Line type="monotone" dataKey="probability" stroke="#e6a65c" strokeWidth={2.5} dot={{ r: 3 }} name="Breach probability" /></LineChart></ResponsiveContainer></div> : <p className="payment-timing-message">Daily breach path unavailable from the risk response.</p>}
              <div className="metric-foot muted">Reserve threshold: {risk?.assumptions?.safety_buffer == null ? "—" : money(risk.assumptions.safety_buffer)} · Mean day if breached: {risk?.time_to_first_buffer_breach?.mean_day_if_breached == null ? "Not observed" : `day ${Number(risk.time_to_first_buffer_breach.mean_day_if_breached).toFixed(1)}`} · Ever-breach rate: {percentage(risk?.time_to_first_buffer_breach?.breach_probability)}</div>
            </article>
          </section>
        )}

        {activePage === "risk-analysis" && (
          <section className="panel payment-timing-panel">
            <div className="panel-header"><div><h2>Historical volatility context</h2><p>Monthly net cash flow from the fictional two-year operating profile</p></div><div className="metric-icon blue"><Activity size={18} /></div></div>
            {historicalRows.length ? <div className="chart-area"><ResponsiveContainer width="100%" height="100%"><BarChart data={historicalRows}><CartesianGrid stroke="#263940" strokeDasharray="3 3" /><XAxis dataKey="period" stroke="#81959c" tick={{ fontSize: 9 }} interval={2} /><YAxis stroke="#81959c" tick={{ fontSize: 10 }} tickFormatter={(value) => `$${Math.round(value / 1000)}k`} /><Tooltip formatter={(value) => money(value)} /><Bar dataKey="net_cash_flow" name="Monthly net cash flow" fill="#79b9f3" /></BarChart></ResponsiveContainer></div> : <p className="payment-timing-message">{businessHistoryError || "Loading historical operating profile…"}</p>}
            <div className="assumption-note"><AlertTriangle size={15} /><span>This 24-month synthetic profile provides context for lumpy business cash flows; it is not fitted to the Nessie account and does not alter this run's Monte Carlo probabilities.</span></div>
          </section>
        )}

        {activePage === "risk-analysis" && (
          <>
        <section className="panel ml-panel">
          <div className="panel-header">
            <div>
              <h2>ML Risk Assessment</h2>
              <p>Random Forest · Scenario classification</p>
            </div>
            <div className="metric-icon purple">
              <Sparkles size={18} />
            </div>
          </div>

          {mlRisk ? (
            <>
              <div className="ml-result">
                <div>
                  <span className="ml-label">MODEL PREDICTION</span>
                  <h3>
                    {mlRisk.prediction === 1
                      ? "Potential shortfall scenario"
                      : "No shortfall predicted"}
                  </h3>
                </div>

                <span
                  className={`ml-badge ${
                    mlRisk.prediction === 1 ? "ml-warning" : "ml-neutral"
                  }`}
                >
                  Class {mlRisk.prediction}
                </span>
              </div>

              <div className="ml-score-row">
                <span>Shortfall-class model score</span>
                <strong>
                  {typeof mlRisk.model_score === "number"
                    ? `${(mlRisk.model_score * 100).toFixed(1)}%`
                    : "Unavailable"}
                </strong>
              </div>

              <div className="ml-score-track">
                <div
                  className="ml-score-fill"
                  style={{
                    width: `${
                      typeof mlRisk.model_score === "number"
                        ? Math.min(
                            100,
                            Math.max(0, mlRisk.model_score * 100)
                          )
                        : 0
                    }%`,
                  }}
                />
              </div>

              <div className="ml-scenario-grid">
                <div>
                  <span>Rule-based baseline</span>
                  <strong>{mlRisk.baseline?.prediction === 1 ? "Shortfall" : "No shortfall"}</strong>
                </div>
                <div>
                  <span>Baseline minimum cash</span>
                  <strong>{money(mlRisk.baseline?.projected_minimum_balance)}</strong>
                </div>
                <div>
                  <span>Model agreement</span>
                  <strong>{mlRisk.agrees_with_baseline ? "Agrees" : "Differs"}</strong>
                </div>
                <div>
                  <span>Baseline inflow rule</span>
                  <strong>Credit only by day 2</strong>
                </div>
              </div>

              <div className="ml-scenario-grid">
                <div>
                  <span>Starting balance</span>
                  <strong>{money(mlRisk.scenario?.starting_balance)}</strong>
                </div>
                <div>
                  <span>Expected inflows</span>
                  <strong>{money(mlRisk.scenario?.expected_inflows)}</strong>
                </div>
                <div>
                  <span>Scheduled outflows</span>
                  <strong>{money(mlRisk.scenario?.scheduled_outflows)}</strong>
                </div>
                <div>
                  <span>Assumed inflow delay</span>
                  <strong>
                    {mlRisk.scenario?.inflow_delay_days ?? "—"} days
                  </strong>
                </div>
              </div>

              <div className="assumption-note">
                <AlertTriangle size={16} />
                <span>
                  {mlRisk.score_interpretation ||
                    "This is a model score, not a calibrated probability."}{" "}
                  The model was trained on synthetic scenarios and is not a
                  calibrated real-world probability of business failure.
                </span>
              </div>
            </>
          ) : (
            <p className="ml-empty">
              {loading
                ? "Loading ML assessment…"
                : "ML assessment unavailable. Refresh the dashboard to try again."}
            </p>
          )}
        </section>

        <section className="panel payment-timing-panel">
          <div className="panel-header">
            <div>
              <h2>Risk Drivers & Stress Tests</h2>
              <p>Event-level attribution and adverse 14-day scenarios</p>
            </div>
            <div className="metric-icon amber"><TrendingDown size={18} /></div>
          </div>
          {riskDrivers && <>
            <div className="whatif-forecast-list">
              {riskDrivers.risk_drivers?.slice(0, 4).map((driver) => (
                <div className="whatif-forecast-row" key={driver.event_id}>
                  <span>{driver.kind} · {driver.event_id} · {money(driver.amount)}</span>
                  <span>{percentage(driver.safety_buffer_breach_probability_contribution)} breach contribution</span>
                </div>
              ))}
            </div>
            <div className="whatif-forecast-list">
              {Object.entries(stressTests?.scenarios || {}).map(([name, result]) => (
                <div className="whatif-forecast-row" key={name}>
                  <span>{name.replaceAll("_", " ")}</span>
                  <span>{percentage(result.metrics?.safety_buffer_breach_probability)} buffer breach</span>
                </div>
              ))}
            </div>
            {stressRows.length > 0 && <>
              <h3 className="detail-subheading">Stress case comparison</h3>
              <div className="chart-area"><ResponsiveContainer width="100%" height="100%"><BarChart data={stressRows} layout="vertical" margin={{ left: 12, right: 24 }}><CartesianGrid stroke="#263940" strokeDasharray="3 3" /><XAxis type="number" domain={[0, 1]} tickFormatter={(value) => `${Math.round(value * 100)}%`} stroke="#81959c" /><YAxis type="category" dataKey="name" width={135} stroke="#81959c" tick={{ fontSize: 10 }} /><Tooltip formatter={(value) => percentage(value)} /><Bar dataKey="probability" name="Buffer breach" fill="#e6a65c" radius={[0, 4, 4, 0]} /></BarChart></ResponsiveContainer></div>
            </>}
          </>}
          {!riskDrivers && <p className="payment-timing-message">{quantError || "Loading risk drivers and stress tests…"}</p>}
          <p className="whatif-disclaimer">Attribution is one-event-at-a-time and contributions are not additive or causal. Stress scenarios are illustrative assumptions, not likelihood forecasts.</p>
        </section>

        <section className="panel payment-timing-panel">
          <div className="panel-header">
            <div>
              <h2>Payment Timing Intelligence</h2>
              <p>Historical settlement-data readiness</p>
            </div>
            <div className="metric-icon blue">
              <CalendarDays size={18} />
            </div>
          </div>

          {paymentTimingLoading ? (
            <p className="payment-timing-message">
              Checking verified settlement history…
            </p>
          ) : paymentTimingError ? (
            <div className="payment-timing-message payment-timing-error">
              <AlertTriangle size={17} />
              <span>{paymentTimingError}</span>
            </div>
          ) : (
            <>
              <div className="payment-timing-status">
                <span className="payment-timing-dot" />
                <div>
                  <strong>
                    {paymentTiming?.status === "available"
                      ? "Historical baseline available"
                      : "Historical baseline unavailable"}
                  </strong>
                  <p>
                    {paymentTiming?.reason ||
                      "Verified settlement history is needed to estimate payment delays."}
                  </p>
                </div>
              </div>

              <div className="ml-scenario-grid payment-timing-grid">
                <div>
                  <span>Verified observations</span>
                  <strong>{paymentTiming?.observations ?? 0}</strong>
                </div>
                <div>
                  <span>Transactions inspected</span>
                  <strong>{paymentTiming?.transactions_inspected ?? "—"}</strong>
                </div>
              </div>

              {paymentTiming?.synthetic_model_evaluation && (
                <div className="ml-scenario-grid payment-timing-grid">
                  <div>
                    <span>Gradient Boosting delay MAE · held-out synthetic payers</span>
                    <strong>{Number(paymentTiming.synthetic_model_evaluation.gradient_boosting_mae_days).toFixed(2)} days</strong>
                  </div>
                  <div>
                    <span>Historical-median baseline MAE</span>
                    <strong>{Number(paymentTiming.synthetic_model_evaluation.median_baseline_mae_days).toFixed(2)} days</strong>
                  </div>
                  <div>
                    <span>Calibrated delay probability Brier · model / baseline</span>
                    <strong>{Number(paymentTiming.synthetic_model_evaluation.calibrated_over_3_day_delay_brier).toFixed(3)} / {Number(paymentTiming.synthetic_model_evaluation.prevalence_baseline_brier).toFixed(3)}</strong>
                  </div>
                  <div>
                    <span>Evaluation sample</span>
                    <strong>{paymentTiming.synthetic_model_evaluation.held_out_rows?.toLocaleString()} rows · {paymentTiming.synthetic_model_evaluation.held_out_payers} payers</strong>
                  </div>
                </div>
              )}

              <div className="assumption-note">
                <AlertTriangle size={16} />
                <span>
                  The optional timing model is trained only on generated payer histories. It modestly improves held-out synthetic classification calibration, but its delay regressor loses to the historical-median baseline and is disabled. Simulations use the synthetic calibrated probability with an explicit limitation; verified Nessie settlement outcomes are still required for business-specific predictions.
                </span>
              </div>
            </>
          )}
        </section>

        <section className="panel payment-timing-panel">
          <div className="panel-header">
            <div>
              <h2>Liquidity Actions</h2>
              <p>{decisionData?.horizon_days || 14}-day common-scenario comparison · {decisionData?.simulations?.toLocaleString() || "—"} simulations · 5% buffer-breach target</p>
            </div>
            <div className="metric-icon green"><ShieldCheck size={18} /></div>
          </div>
          {decisionData?.comparisons?.[0]?.daily_balance_percentiles && (
            <div className="chart-area" role="img" aria-label="Simulated cash balance fan chart">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={Object.entries(decisionData.comparisons[0].daily_balance_percentiles).map(([day, values]) => ({ day: `Day ${day}`, ...values }))}>
                  <CartesianGrid stroke="#263940" strokeDasharray="3 3" />
                  <XAxis dataKey="day" stroke="#81959c" tick={{ fontSize: 10 }} />
                  <YAxis stroke="#81959c" tick={{ fontSize: 10 }} tickFormatter={(value) => `$${Math.round(value / 1000)}k`} />
                  <Tooltip formatter={(value) => money(value)} />
                  <Area type="monotone" dataKey="p95" stroke="#42d6a0" fill="#42d6a0" fillOpacity={0.08} name="95th percentile" />
                  <Area type="monotone" dataKey="p50" stroke="#79b9f3" fill="none" name="Median" />
                  <Area type="monotone" dataKey="p05" stroke="#edbb68" fill="none" name="5th percentile" />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          )}
          {decisionData ? (
            <>
              {decisionData.recommended_action ? (
                <div className="payment-timing-status">
                  <span className="payment-timing-dot" />
                  <div>
                    <strong>Lowest-cost feasible action: {decisionData.recommended_action.name}</strong>
                    <p>Estimated cost {money(decisionData.recommended_action.cost)} · buffer-breach risk {percentage(decisionData.recommended_action.safety_buffer_breach_probability)}</p>
                  </div>
                </div>
              ) : <p className="payment-timing-message">No tested action meets the risk target with the current scheduled events.</p>}
              <div className="whatif-forecast-list">
                {decisionData.comparisons?.map((item) => (
                  <div className="whatif-forecast-row" key={item.name}>
                    <span>{item.name} · cost {money(item.cost)}</span>
                    <span>{percentage(item.safety_buffer_breach_probability)} breach · {money(item.cvar_95)} CVaR</span>
                  </div>
                ))}
              </div>
              {actionRows.length > 0 && <>
                <h3 className="detail-subheading">Cost versus residual risk</h3>
                <div className="chart-area"><ResponsiveContainer width="100%" height="100%"><BarChart data={actionRows}><CartesianGrid stroke="#263940" strokeDasharray="3 3" /><XAxis dataKey="name" stroke="#81959c" tick={{ fontSize: 9 }} interval={0} /><YAxis yAxisId="risk" domain={[0, 1]} stroke="#81959c" tickFormatter={(value) => `${Math.round(value * 100)}%`} /><YAxis yAxisId="cost" orientation="right" stroke="#81959c" tickFormatter={(value) => `$${Math.round(value)}`} /><Tooltip formatter={(value, name) => [name === "Risk" ? percentage(value) : money(value), name]} /><Legend /><Bar yAxisId="risk" dataKey="risk" name="Risk" fill="#e6a65c" radius={[4, 4, 0, 0]} /><Bar yAxisId="cost" dataKey="cost" name="Cost" fill="#42d6a0" radius={[4, 4, 0, 0]} /></BarChart></ResponsiveContainer></div>
              </>}
              <p className="whatif-disclaimer">
                Illustrative cost assumptions: defer {percentage(decisionData.assumptions?.deferral_fee_rate)} of payment amount; accelerate {percentage(decisionData.assumptions?.acceleration_fee_rate)}; credit line up to {money(decisionData.assumptions?.credit_line_limit)} with {percentage(decisionData.assumptions?.credit_line_fee_rate)} fee. These are planning placeholders, not lender quotes. Unexpected expenses: {percentage(decisionData.assumptions?.unexpected_expense_probability)} daily chance, up to {money(decisionData.assumptions?.max_unexpected_expense)}.
              </p>
            </>
          ) : <p className="payment-timing-message">{decisionError || "Loading intervention comparison…"}</p>}
        </section>

        <section className="panel whatif-panel">
          <div className="panel-header">
            <div>
              <h2>What-if Simulator</h2>
              <p>Test cash-flow changes before they happen</p>
            </div>
            <div className="metric-icon blue">
              <SlidersHorizontal size={18} />
            </div>
          </div>

          <form className="whatif-form" onSubmit={runWhatIf}>
            <div className="whatif-fields">
              <label className="whatif-field">
                <span>Upcoming payroll ($)</span>
                <input
                  type="number"
                  min="0"
                  max="10000000"
                  step="100"
                  value={whatIfInputs.payroll_amount}
                  onChange={(event) =>
                    updateWhatIfInput("payroll_amount", event.target.value)
                  }
                  required
                />
                <small>Scheduled withdrawal in the scenario</small>
              </label>

              <label className="whatif-field">
                <span>Expected deposit ($)</span>
                <input
                  type="number"
                  min="0"
                  max="10000000"
                  step="100"
                  value={whatIfInputs.deposit_amount}
                  onChange={(event) =>
                    updateWhatIfInput("deposit_amount", event.target.value)
                  }
                  required
                />
                <small>Expected customer payment</small>
              </label>

              <label className="whatif-field">
                <span>Deposit delay</span>
                <select
                  value={whatIfInputs.deposit_delay_days}
                  onChange={(event) =>
                    updateWhatIfInput("deposit_delay_days", event.target.value)
                  }
                >
                  <option value={0}>On time (0 days)</option>
                  <option value={1}>1 day late</option>
                  <option value={2}>2 days late</option>
                  <option value={3}>3 days late</option>
                  <option value={4}>4 days late</option>
                  <option value={5}>5 days late</option>
                  <option value={6}>6 days late</option>
                  <option value={7}>7 days late</option>
                </select>
                <small>Delay applied to the expected deposit</small>
              </label>

              <label className="whatif-field">
                <span>Safety buffer ($)</span>
                <input
                  type="number"
                  min="0"
                  max="10000000"
                  step="250"
                  value={whatIfInputs.safety_buffer}
                  onChange={(event) =>
                    updateWhatIfInput("safety_buffer", event.target.value)
                  }
                  required
                />
                <small>Minimum desired cash reserve</small>
              </label>
            </div>

            <div className="whatif-actions">
              <button
                className="whatif-run"
                type="submit"
                disabled={whatIfLoading}
              >
                <Play size={15} />
                {whatIfLoading ? "Simulating..." : "Run scenario"}
              </button>
              <button
                className="whatif-reset"
                type="button"
                onClick={resetWhatIf}
                disabled={whatIfLoading}
              >
                <RotateCcw size={14} />
                Reset
              </button>
            </div>
          </form>

          {whatIfError && (
            <div className="whatif-error">
              <AlertTriangle size={16} />
              <span>{whatIfError}</span>
            </div>
          )}

          {whatIfResult && (
            <div className="whatif-results">
              <div className="whatif-results-heading">
                <div>
                  <h3>Scenario results</h3>
                  <p>
                    Based on {Number(whatIfResult.monte_carlo?.simulations ?? 0).toLocaleString()} simulated paths
                  </p>
                </div>
                <span className="whatif-result-tag">What-if estimate</span>
              </div>

              <div className="whatif-metrics">
                <div className="whatif-metric">
                  <span>Projected ending balance</span>
                  <strong>{money(whatIfResult.projected_ending_balance)}</strong>
                </div>
                <div className="whatif-metric">
                  <span>Safety-buffer breach</span>
                  <strong>{percentage(whatIfResult.monte_carlo?.safety_buffer_breach_probability)}</strong>
                </div>
                <div className="whatif-metric">
                  <span>Actual cash shortfall</span>
                  <strong>{percentage(whatIfResult.monte_carlo?.shortfall_probability)}</strong>
                </div>
                <div className="whatif-metric">
                  <span>Downside estimate · P05</span>
                  <strong>{money(whatIfResult.monte_carlo?.ending_balance_p05)}</strong>
                </div>
              </div>

              {Array.isArray(whatIfResult.forecast) && whatIfResult.forecast.length > 0 && (
                <div className="whatif-forecast">
                  <h4>Scenario cash-flow path</h4>
                  <div className="whatif-forecast-list">
                    {whatIfResult.forecast.map((day) => (
                      <div className="whatif-forecast-row" key={day.day}>
                        <span>{day.label}</span>
                        <span>{money(day.projected_balance)}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {whatIfResult.briefing && (
                <div className="whatif-briefing">
                  <h4><Sparkles size={15} /> Gemini scenario analysis</h4>
                  <ReactMarkdown
                    components={{
                      h2: ({ children }) => <h5>{children}</h5>,
                      h3: ({ children }) => <h5>{children}</h5>,
                      p: ({ children }) => <p>{children}</p>,
                      ul: ({ children }) => <ul>{children}</ul>,
                      ol: ({ children }) => <ol>{children}</ol>,
                      li: ({ children }) => <li>{children}</li>,
                    }}
                  >
                    {whatIfResult.briefing}
                  </ReactMarkdown>
                </div>
              )}

              <p className="whatif-disclaimer">
                Scenario outputs depend on assumptions and are not guarantees or calibrated real-world probabilities.
              </p>
            </div>
          )}
        </section>
          </>
        )}

        {activePage === "help-methodology" && (
          <>
        <section className="metric-grid methodology-metrics">
          <article className="metric-card"><div className="metric-top"><span>Cash-flow baseline</span></div><div className="metric-value">Daily ledger</div><div className="metric-foot muted">Pending outflows subtracted; pending receipts held out</div></article>
          <article className="metric-card"><div className="metric-top"><span>Scenario engine</span></div><div className="metric-value">Monte Carlo</div><div className="metric-foot muted">{risk?.simulations?.toLocaleString() || "—"} paths · {risk?.horizon_days || forecast.length - 1 || "—"}-day horizon</div></article>
          <article className="metric-card"><div className="metric-top"><span>Risk classifier</span></div><div className="metric-value">Random Forest</div><div className="metric-foot muted">Synthetic training scenarios; score is not calibrated</div></article>
          <article className="metric-card"><div className="metric-top"><span>Payment timing</span></div><div className="metric-value">{paymentTiming?.status === "available" ? "History available" : "Synthetic eval"}</div><div className="metric-foot muted">Real settlement history is needed for payer-specific estimates</div></article>
        </section>
        <section className="content-grid page-view methodology-grid">
          <article className="panel"><div className="panel-header"><div><h2>How the prediction pipeline works</h2><p>Inputs flow into transparent scenario estimates</p></div><div className="metric-icon purple"><Sparkles size={18} /></div></div>
            <ol className="method-steps"><li><strong>Ledger normalization</strong><span>Account balance plus dated pending and scheduled events are reconciled into a shared event view.</span></li><li><strong>Timing uncertainty</strong><span>Payment-timing evaluation reports synthetic holdout results; verified Nessie settlement outcomes remain limited.</span></li><li><strong>Path simulation</strong><span>Monte Carlo samples payment clearing, expense shocks, and outflow variation across the configured horizon.</span></li><li><strong>Decision comparison</strong><span>Candidate actions reuse common scenario draws so risk changes can be compared consistently.</span></li></ol>
          </article>
          <article className="panel"><div className="panel-header"><div><h2>Assumptions in this run</h2><p>Configured scenario parameters from the risk response</p></div><div className="metric-icon amber"><AlertTriangle size={18} /></div></div>
            <div className="whatif-forecast-list"><div className="whatif-forecast-row"><span>Horizon</span><strong>{risk?.horizon_days ?? "—"} days</strong></div><div className="whatif-forecast-row"><span>Simulation count</span><strong>{risk?.simulations?.toLocaleString() ?? "—"}</strong></div><div className="whatif-forecast-row"><span>Reserve threshold</span><strong>{risk?.assumptions?.safety_buffer == null ? "—" : money(risk.assumptions.safety_buffer)}</strong></div><div className="whatif-forecast-row"><span>Inflow clear probability</span><strong>{percentage(risk?.assumptions?.deposit_clear_probability)}</strong></div><div className="whatif-forecast-row"><span>Maximum inflow delay</span><strong>{risk?.assumptions?.max_deposit_delay_days ?? "—"} days</strong></div><div className="whatif-forecast-row"><span>Unexpected expense chance / day</span><strong>{percentage(risk?.assumptions?.unexpected_expense_probability)}</strong></div><div className="whatif-forecast-row"><span>Maximum unexpected expense</span><strong>{risk?.assumptions?.max_unexpected_expense == null ? "—" : money(risk.assumptions.max_unexpected_expense)}</strong></div></div>
          </article>
        </section>
        <section className="panel briefing-panel">
          <div className="panel-header">
            <div>
              <h2>Gemini Financial Briefing</h2>
              <p>AI-powered analysis of your financial outlook</p>
            </div>
            <div className="metric-icon purple">
              <Sparkles size={18} />
            </div>
          </div>

          {briefingLoading ? (
            <p className="briefing-status">
              <Sparkles size={16} />
              Analyzing cash flow and risk metrics...
            </p>
          ) : briefingError ? (
            <div className="briefing-error">
              <AlertTriangle size={17} />
              <span>{briefingError}</span>
              <button onClick={loadBriefing}>Retry</button>
            </div>
          ) : briefing ? (
            <div className="briefing-content">
              <ReactMarkdown
                components={{
                  h2: ({ children }) => <h3>{children}</h3>,
                  h3: ({ children }) => <h3>{children}</h3>,
                  p: ({ children }) => <p>{children}</p>,
                  ul: ({ children }) => <ul>{children}</ul>,
                  ol: ({ children }) => <ol>{children}</ol>,
                  li: ({ children }) => <li>{children}</li>,
                }}
              >
                {briefing.replace(/\\n/g, "\n").replace(/\r\n/g, "\n")}
              </ReactMarkdown>
            </div>
          ) : (
            <p className="briefing-status">
              No briefing is available yet.
            </p>
          )}

          <div className="briefing-footer">
            <span>
              <Sparkles size={14} />
              Powered by Gemini
            </span>
            <button
              onClick={loadBriefing}
              disabled={briefingLoading}
            >
              <RefreshCw size={14} />
              {briefingLoading ? "Generating..." : "Refresh briefing"}
            </button>
          </div>
        </section>
          </>
        )}

        {activePage === "transactions" && (
        <section className="panel transactions-panel page-anchor" id="transactions">
          <div className="panel-header">
            <div>
              <h2>Upcoming transactions</h2>
              <p>
                Simulated activity from the Nessie sandbox account
              </p>
            </div>

            <button
              className="text-button"
              onClick={loadDashboard}
              disabled={loading}
            >
              <RefreshCw size={14} />
              {loading ? "Refreshing…" : "Refresh data"}
            </button>
          </div>

          <div className="ml-scenario-grid payment-timing-grid">
            <div><span>Scheduled receipts in forecast</span><strong>{money(scheduledInflows)}</strong></div>
            <div><span>Pending / scheduled obligations</span><strong>{money(scheduledOutflows)}</strong></div>
            <div><span>Net scheduled movement</span><strong>{money(scheduledInflows - scheduledOutflows)}</strong></div>
            <div><span>Ledger horizon</span><strong>{forecast.length ? `${forecast.length - 1} days` : "Unavailable"}</strong></div>
          </div>
          <h3 className="detail-subheading">Monthly business volume · 24 months</h3>
          {historicalRows.length ? <div className="chart-area"><ResponsiveContainer width="100%" height="100%"><BarChart data={historicalRows}><CartesianGrid stroke="#263940" strokeDasharray="3 3" /><XAxis dataKey="period" stroke="#81959c" tick={{ fontSize: 9 }} interval={2} /><YAxis stroke="#81959c" tick={{ fontSize: 10 }} tickFormatter={(value) => `$${Math.round(value / 1000)}k`} /><Tooltip formatter={(value) => money(value)} /><Legend /><Bar dataKey="revenue" name="Receipts" fill="#42d6a0" /><Bar dataKey="expenses" name="Expenses" fill="#e6a65c" /></BarChart></ResponsiveContainer></div> : <p className="payment-timing-message">{businessHistoryError || "Loading monthly history…"}</p>}
          <h3 className="detail-subheading">Scheduled ledger activity by day</h3>
          {forecast.length ? <div className="chart-area"><ResponsiveContainer width="100%" height="100%"><BarChart data={forecastFlowRows}><CartesianGrid stroke="#263940" strokeDasharray="3 3" /><XAxis dataKey="date" stroke="#81959c" tick={{ fontSize: 10 }} /><YAxis stroke="#81959c" tick={{ fontSize: 10 }} tickFormatter={(value) => `$${Math.round(value / 1000)}k`} /><Tooltip formatter={(value) => money(value)} /><Legend /><Bar dataKey="scheduled_inflows" name="Expected receipts" fill="#42d6a0" radius={[4, 4, 0, 0]} /><Bar dataKey="scheduled_outflows" name="Obligations" fill="#e6a65c" radius={[4, 4, 0, 0]} /></BarChart></ResponsiveContainer></div> : <p className="payment-timing-message">{loading ? "Loading scheduled activity…" : "No ledger activity available."}</p>}

          <div className="transaction-row">
            <div className="transaction-symbol payroll">
              <ArrowDownRight size={18} />
            </div>

            <div className="transaction-main">
              <strong>Simulated upcoming payroll</strong>
              <span>Withdrawal · Oct 20, 2026</span>
            </div>

            <span className="transaction-status">Pending</span>
            <strong className="transaction-amount negative">
              −$7,000
            </strong>
          </div>

          <div className="transaction-row">
            <div className="transaction-symbol deposit">
              <ArrowUpRight size={18} />
            </div>

            <div className="transaction-main">
              <strong>Expected customer payment</strong>
              <span>Deposit · Pending</span>
            </div>

            <span className="transaction-status">Pending</span>
            <strong className="transaction-amount positive">
              +$3,000
            </strong>
          </div>
          <div className="history-header"><h3>Two-year transaction history</h3><span>{businessHistory?.summary?.transaction_count?.toLocaleString() || "—"} generated entries · synthetic demo profile</span></div>
          {recentHistoricalTransactions.length ? <div className="history-table-wrap"><table className="history-table"><thead><tr><th>Settlement date</th><th>Counterparty / memo</th><th>Category</th><th>Status</th><th className="numeric">Amount</th></tr></thead><tbody>{recentHistoricalTransactions.map((item) => <tr key={item.transaction_id}><td>{item.date}</td><td><strong>{item.counterparty}</strong><small>{item.description}</small></td><td>{item.category}</td><td><span className={`history-status ${item.direction}`}>{item.status}</span></td><td className={`numeric ${item.direction === "inflow" ? "positive-text" : "negative-text"}`}>{item.direction === "inflow" ? "+" : "−"}{money(item.amount)}</td></tr>)}</tbody></table></div> : <p className="payment-timing-message">{businessHistoryError || "Loading generated history…"}</p>}
          <div className="assumption-note"><AlertTriangle size={15} /><span>{businessHistory?.disclosure || "Synthetic sample only; these transactions are not retrieved from Nessie."}</span></div>
        </section>
        )}

        {activePage === "help-methodology" && (
        <footer className="footer page-anchor" id="help-methodology">
          <span>
            NESSHIELD AI{" "}
            <span className="footer-dot">·</span>{" "}
            FINANCIAL INTELLIGENCE
          </span>

          <span>
            {loading
              ? "Updating data…"
              : connected
                ? "Connected to Nessie sandbox"
                : "Live data unavailable"}
            <span className="footer-dot">·</span>
            Scenario outputs are estimates, not guarantees.
          </span>
        </footer>
        )}
      </main>
    </div>
  );
}

export default App;
