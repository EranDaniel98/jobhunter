"use client";

import type { PipelineStatsResponse } from "@/lib/types";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts";

interface PipelineChartProps {
  data: PipelineStatsResponse;
}

export function PipelineChart({ data }: PipelineChartProps) {
  const chartData = [
    { name: "Suggested", value: data.suggested, fill: "var(--chart-1)" },
    { name: "Approved", value: data.approved, fill: "var(--chart-2)" },
    { name: "Researched", value: data.researched, fill: "var(--chart-3)" },
    { name: "Contacted", value: data.contacted, fill: "var(--chart-4)" },
    { name: "Rejected", value: data.rejected, fill: "var(--destructive)" },
  ];

  return (
    <ResponsiveContainer width="100%" height={250}>
      <BarChart data={chartData} layout="vertical">
        <CartesianGrid strokeDasharray="3 3" horizontal={false} />
        <XAxis type="number" />
        <YAxis type="category" dataKey="name" width={80} tick={{ fontSize: 12 }} />
        <Tooltip />
        <Bar dataKey="value" radius={[0, 4, 4, 0]} />
      </BarChart>
    </ResponsiveContainer>
  );
}
