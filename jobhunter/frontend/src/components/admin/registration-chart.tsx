"use client";

import type { RegistrationTrend } from "@/lib/types";
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts";

interface RegistrationChartProps {
  data: RegistrationTrend[];
}

export function RegistrationChart({ data }: RegistrationChartProps) {
  const formatted = data.map((d) => ({
    ...d,
    label: new Date(d.date).toLocaleDateString("en-US", {
      month: "short",
      day: "numeric",
    }),
  }));

  return (
    <ResponsiveContainer width="100%" height={300}>
      <AreaChart data={formatted}>
        <CartesianGrid strokeDasharray="3 3" vertical={false} />
        <XAxis dataKey="label" tick={{ fontSize: 12 }} />
        <YAxis allowDecimals={false} />
        <Tooltip />
        <Area
          type="monotone"
          dataKey="count"
          stroke="hsl(210, 70%, 55%)"
          fill="hsl(210, 70%, 55%)"
          fillOpacity={0.2}
          name="Signups"
        />
      </AreaChart>
    </ResponsiveContainer>
  );
}
