import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

/**
 * Renders the public aggregate time-series for a run: average market price,
 * average consumer surplus, and average collusion indicator over time.
 */
export default function SummaryCharts({ summary }) {
  const data = summary.avg_market_price_by_timestep.map((price, i) => ({
    t: i,
    price,
    surplus: summary.avg_consumer_surplus_by_timestep[i],
    collusion: summary.avg_collusion_indicator_by_timestep[i],
  }));

  return (
    <div className="charts">
      <ChartCard title="Average market price">
        <Series data={data} dataKey="price" color="#2563eb" />
      </ChartCard>
      <ChartCard title="Average consumer surplus">
        <Series data={data} dataKey="surplus" color="#059669" />
      </ChartCard>
      <ChartCard title="Average collusion indicator" domain={[0, 1]}>
        <Series data={data} dataKey="collusion" color="#dc2626" />
      </ChartCard>
    </div>
  );
}

function ChartCard({ title, children }) {
  return (
    <div className="chart-card">
      <h4>{title}</h4>
      {children}
    </div>
  );
}

function Series({ data, dataKey, color, domain }) {
  return (
    <ResponsiveContainer width="100%" height={200}>
      <LineChart data={data} margin={{ top: 8, right: 12, left: 0, bottom: 0 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#eef2f7" />
        <XAxis
          dataKey="t"
          tick={{ fontSize: 11 }}
          label={{ value: "timestep", position: "insideBottom", offset: -2, fontSize: 11 }}
        />
        <YAxis tick={{ fontSize: 11 }} domain={domain || ["auto", "auto"]} width={48} />
        <Tooltip />
        <Line
          type="monotone"
          dataKey={dataKey}
          stroke={color}
          strokeWidth={2}
          dot={false}
          isAnimationActive={false}
        />
      </LineChart>
    </ResponsiveContainer>
  );
}
