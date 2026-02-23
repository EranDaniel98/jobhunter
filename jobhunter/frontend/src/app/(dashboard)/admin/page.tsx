"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/providers/auth-provider";
import {
  useSystemOverview,
  useAdminUsers,
  useRegistrationTrend,
  useInviteChain,
  useTopUsers,
} from "@/lib/hooks/use-admin";
import { PageHeader } from "@/components/shared/page-header";
import { CardSkeleton, TableSkeleton } from "@/components/shared/loading-skeleton";
import { OverviewStats } from "@/components/admin/overview-stats";
import { RegistrationChart } from "@/components/admin/registration-chart";
import { UsersTable } from "@/components/admin/users-table";
import { InviteChain } from "@/components/admin/invite-chain";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { ChevronLeft, ChevronRight } from "lucide-react";

const PAGE_SIZE = 20;

export default function AdminPage() {
  const { user, isLoading: authLoading } = useAuth();
  const router = useRouter();
  const [search, setSearch] = useState("");
  const [debouncedSearch, setDebouncedSearch] = useState("");
  const [page, setPage] = useState(0);

  useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedSearch(search);
      setPage(0);
    }, 300);
    return () => clearTimeout(timer);
  }, [search]);

  const overviewQuery = useSystemOverview();
  const usersQuery = useAdminUsers({
    skip: page * PAGE_SIZE,
    limit: PAGE_SIZE,
    search: debouncedSearch || undefined,
  });
  const trendQuery = useRegistrationTrend(30);
  const invitesQuery = useInviteChain();
  const topUsersQuery = useTopUsers("messages_sent", 5);

  // Guard: redirect non-admin users
  if (!authLoading && user && !user.is_admin) {
    router.push("/dashboard");
    return null;
  }

  if (authLoading) {
    return (
      <div className="space-y-6">
        <PageHeader title="Admin" />
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
          <CardSkeleton />
          <CardSkeleton />
          <CardSkeleton />
          <CardSkeleton />
        </div>
      </div>
    );
  }

  const totalPages = Math.ceil((usersQuery.data?.total || 0) / PAGE_SIZE);

  return (
    <div className="space-y-6">
      <PageHeader title="Admin Dashboard" description="Manage users and monitor platform health" />

      <Tabs defaultValue="overview">
        <TabsList>
          <TabsTrigger value="overview">Overview</TabsTrigger>
          <TabsTrigger value="users">Users</TabsTrigger>
          <TabsTrigger value="invites">Invites</TabsTrigger>
        </TabsList>

        <TabsContent value="overview" className="space-y-6 mt-4">
          {overviewQuery.isLoading ? (
            <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
              <CardSkeleton />
              <CardSkeleton />
              <CardSkeleton />
              <CardSkeleton />
            </div>
          ) : overviewQuery.data ? (
            <OverviewStats data={overviewQuery.data} />
          ) : null}

          <div className="grid gap-6 md:grid-cols-2">
            <Card>
              <CardHeader>
                <CardTitle>Registration Trend (30d)</CardTitle>
              </CardHeader>
              <CardContent>
                {trendQuery.isLoading ? (
                  <div className="h-[300px] flex items-center justify-center text-muted-foreground">
                    Loading...
                  </div>
                ) : trendQuery.data && trendQuery.data.length > 0 ? (
                  <RegistrationChart data={trendQuery.data} />
                ) : (
                  <p className="text-sm text-muted-foreground py-8 text-center">
                    No registrations in the last 30 days.
                  </p>
                )}
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>Top Users by Messages Sent</CardTitle>
              </CardHeader>
              <CardContent>
                {topUsersQuery.isLoading ? (
                  <TableSkeleton rows={5} />
                ) : topUsersQuery.data && topUsersQuery.data.length > 0 ? (
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>User</TableHead>
                        <TableHead className="text-right">Messages</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {topUsersQuery.data.map((u, i) => (
                        <TableRow key={i}>
                          <TableCell>
                            <div className="font-medium">{u.full_name}</div>
                            <div className="text-xs text-muted-foreground">{u.email}</div>
                          </TableCell>
                          <TableCell className="text-right font-medium">
                            {u.metric_value}
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                ) : (
                  <p className="text-sm text-muted-foreground py-8 text-center">
                    No message activity yet.
                  </p>
                )}
              </CardContent>
            </Card>
          </div>
        </TabsContent>

        <TabsContent value="users" className="space-y-4 mt-4">
          <div className="flex items-center gap-4">
            <Input
              placeholder="Search by name or email..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="max-w-sm"
            />
          </div>

          {usersQuery.isLoading ? (
            <TableSkeleton rows={10} />
          ) : usersQuery.data ? (
            <>
              <UsersTable users={usersQuery.data.users} currentUserId={user?.id || ""} />
              {totalPages > 1 && (
                <div className="flex items-center justify-between">
                  <p className="text-sm text-muted-foreground">
                    {usersQuery.data.total} total users
                  </p>
                  <div className="flex items-center gap-2">
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => setPage((p) => Math.max(0, p - 1))}
                      disabled={page === 0}
                    >
                      <ChevronLeft className="h-4 w-4" />
                    </Button>
                    <span className="text-sm">
                      Page {page + 1} of {totalPages}
                    </span>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => setPage((p) => p + 1)}
                      disabled={page >= totalPages - 1}
                    >
                      <ChevronRight className="h-4 w-4" />
                    </Button>
                  </div>
                </div>
              )}
            </>
          ) : null}
        </TabsContent>

        <TabsContent value="invites" className="mt-4">
          <Card>
            <CardHeader>
              <CardTitle>Invite Chain</CardTitle>
            </CardHeader>
            <CardContent>
              {invitesQuery.isLoading ? (
                <TableSkeleton rows={5} />
              ) : invitesQuery.data ? (
                <InviteChain data={invitesQuery.data} />
              ) : null}
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}
