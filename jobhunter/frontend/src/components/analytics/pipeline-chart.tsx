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
    { name: "Suggested", value: data.suggested, fill: "hsl(210, 70%, 55%)" },
    { name: "Approved", value: data.approved, fill: "hsl(142, 60%, 45%)" },
    { name: "Researched", value: data.researched, fill: "hsl(262, 50%, 55%)" },
    { name: "Contacted", value: data.contacted, fill: "hsl(45, 80%, 50%)" },
    { name: "Rejected", value: data.rejected, fill: "hsl(0, 60%, 55%)" },
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
