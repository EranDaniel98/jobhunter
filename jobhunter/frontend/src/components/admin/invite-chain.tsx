"use client";

import type { InviteChainItem } from "@/lib/types";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";

interface InviteChainProps {
  data: InviteChainItem[];
}

export function InviteChain({ data }: InviteChainProps) {
  if (data.length === 0) {
    return (
      <p className="text-sm text-muted-foreground py-8 text-center">
        No invite activity yet.
      </p>
    );
  }

  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>Invited By</TableHead>
          <TableHead>Invitee</TableHead>
          <TableHead>Code</TableHead>
          <TableHead>Status</TableHead>
          <TableHead>Used At</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {data.map((item, i) => (
          <TableRow key={i}>
            <TableCell>
              <div>
                <div className="font-medium">{item.inviter_name}</div>
                <div className="text-xs text-muted-foreground">{item.inviter_email}</div>
              </div>
            </TableCell>
            <TableCell>
              {item.invitee_name ? (
                <div>
                  <div className="font-medium">{item.invitee_name}</div>
                  <div className="text-xs text-muted-foreground">{item.invitee_email}</div>
                </div>
              ) : (
                <span className="text-muted-foreground">-</span>
              )}
            </TableCell>
            <TableCell>
              <code className="text-xs bg-muted px-1.5 py-0.5 rounded">
                {item.code}
              </code>
            </TableCell>
            <TableCell>
              <Badge variant={item.used_at ? "default" : "secondary"}>
                {item.used_at ? "Used" : "Pending"}
              </Badge>
            </TableCell>
            <TableCell className="text-sm text-muted-foreground">
              {item.used_at
                ? new Date(item.used_at).toLocaleDateString()
                : "-"}
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}
