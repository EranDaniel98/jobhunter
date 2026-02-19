"use client";

import type { FunnelResponse } from "@/lib/types";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Cell,
} from "recharts";

interface FunnelChartProps {
  data: FunnelResponse;
}

const COLORS = [
  "hsl(210, 70%, 55%)",
  "hsl(200, 65%, 50%)",
  "hsl(180, 60%, 45%)",
  "hsl(142, 60%, 45%)",
  "hsl(120, 55%, 40%)",
  "hsl(0, 60%, 55%)",
];

export function FunnelChart({ data }: FunnelChartProps) {
  const chartData = [
    { name: "Drafted", value: data.drafted },
    { name: "Sent", value: data.sent },
    { name: "Delivered", value: data.delivered },
    { name: "Opened", value: data.opened },
    { name: "Replied", value: data.replied },
    { name: "Bounced", value: data.bounced },
  ];

  return (
    <ResponsiveContainer width="100%" height={250}>
      <BarChart data={chartData}>
        <CartesianGrid strokeDasharray="3 3" vertical={false} />
        <XAxis dataKey="name" tick={{ fontSize: 12 }} />
        <YAxis />
        <Tooltip />
        <Bar dataKey="value" radius={[4, 4, 0, 0]}>
          {chartData.map((_, index) => (
            <Cell key={index} fill={COLORS[index]} />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}
