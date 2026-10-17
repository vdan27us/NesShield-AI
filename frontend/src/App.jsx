
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
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import "./App.css";

const API = "http://127.0.0.1:8000";

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

const formatDate = (dateString) => {
  if (!dateString) return "Date unavailable";

  const date = new Date(`${dateString}T12:00:00`);

  if (Number.isNaN(date.getTime())) return dateString;

  return date.toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
  });
};

function App() {
  const [account, setAccount] = useState(null);
  const [forecast, setForecast] = useState([]);
  const [risk, setRisk] = useState(null);
  const [mlRisk, setMlRisk] = useState(null);
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
    loadDashboard();
  }, [loadDashboard]);

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
    loadBriefing();
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

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-mark">
            <ShieldCheck size={25} />
          </div>

          <div>
            <div className="brand-name">
              nesshield<span>AI</span>
            </div>
            <div className="brand-subtitle">
              FINANCIAL INTELLIGENCE
            </div>
          </div>
        </div>

        <div className="nav-label">WORKSPACE</div>

        <nav>
          <div className="nav-item active">
            <LayoutDashboard size={18} />
            Overview
          </div>
          <div className="nav-item">
            <Activity size={18} />
            Cash flow
          </div>
          <div className="nav-item">
            <TrendingDown size={18} />
            Risk analysis
          </div>
          <div className="nav-item">
            <Wallet size={18} />
            Transactions
          </div>
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

          <div className="nav-item">
            <CircleHelp size={18} />
            Help & methodology
          </div>
        </div>
      </aside>

      <main className="main-content">
        <header className="topbar">
          <div>
            <div className="eyebrow">
              BUSINESS OVERVIEW / CASH POSITION
            </div>
            <h1>
              Good afternoon <span className="wave">✳</span>
            </h1>
            <p className="page-subtitle">
              Here's your financial outlook and risk snapshot.
            </p>
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

        <section className="hero-card">
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

        <section className="content-grid">
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
        </section>

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

        <section className="panel transactions-panel">
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
        </section>

        <footer className="footer">
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
      </main>
    </div>
  );
}

export default App;
