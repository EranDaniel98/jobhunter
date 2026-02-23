"use client";

import { memo, useState } from "react";
import type { AdminUser } from "@/lib/types";
import { useToggleAdmin, useDeleteUser, useToggleActive } from "@/lib/hooks/use-admin";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { MoreHorizontal, Shield, ShieldOff, Trash2, UserCheck, UserX } from "lucide-react";
import { toast } from "sonner";

interface UsersTableProps {
  users: AdminUser[];
  currentUserId: string;
  onSelectUser?: (id: string) => void;
}

function UsersTableInner({ users, currentUserId, onSelectUser }: UsersTableProps) {
  const [deleteTarget, setDeleteTarget] = useState<AdminUser | null>(null);
  const toggleAdmin = useToggleAdmin();
  const toggleActive = useToggleActive();
  const deleteUser = useDeleteUser();

  const handleToggleAdmin = (user: AdminUser) => {
    toggleAdmin.mutate(
      { id: user.id, isAdmin: !user.is_admin },
      {
        onSuccess: () => {
          toast.success(
            user.is_admin
              ? `Removed admin from ${user.full_name}`
              : `Made ${user.full_name} admin`
          );
        },
        onError: () => toast.error("Failed to update admin status"),
      }
    );
  };

  const handleToggleActive = (user: AdminUser) => {
    toggleActive.mutate(
      { id: user.id, isActive: !user.is_active },
      {
        onSuccess: () => {
          toast.success(
            user.is_active
              ? `Suspended ${user.full_name}`
              : `Activated ${user.full_name}`
          );
        },
        onError: () => toast.error("Failed to update status"),
      }
    );
  };

  const handleDelete = () => {
    if (!deleteTarget) return;
    deleteUser.mutate(deleteTarget.id, {
      onSuccess: () => {
        toast.success(`Deleted ${deleteTarget.full_name}`);
        setDeleteTarget(null);
      },
      onError: () => toast.error("Failed to delete user"),
    });
  };

  return (
    <>
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Name</TableHead>
            <TableHead>Email</TableHead>
            <TableHead>Joined</TableHead>
            <TableHead className="text-right">Companies</TableHead>
            <TableHead className="text-right">Messages</TableHead>
            <TableHead>Status</TableHead>
            <TableHead className="w-[50px]" />
          </TableRow>
        </TableHeader>
        <TableBody>
          {users.map((user) => (
            <TableRow
              key={user.id}
              className={onSelectUser ? "cursor-pointer" : ""}
              onClick={() => onSelectUser?.(user.id)}
            >
              <TableCell className="font-medium">{user.full_name}</TableCell>
              <TableCell className="text-muted-foreground">{user.email}</TableCell>
              <TableCell className="text-muted-foreground">
                {new Date(user.created_at).toLocaleDateString()}
              </TableCell>
              <TableCell className="text-right">{user.companies_count}</TableCell>
              <TableCell className="text-right">{user.messages_sent_count}</TableCell>
              <TableCell>
                <div className="flex gap-1">
                  {user.is_admin && (
                    <Badge variant="default" className="gap-1">
                      <Shield className="h-3 w-3" />
                      Admin
                    </Badge>
                  )}
                  {!user.is_active && (
                    <Badge variant="destructive">Suspended</Badge>
                  )}
                </div>
              </TableCell>
              <TableCell>
                <DropdownMenu>
                  <DropdownMenuTrigger asChild>
                    <Button
                      variant="ghost"
                      size="icon"
                      className="h-8 w-8"
                      onClick={(e) => e.stopPropagation()}
                    >
                      <MoreHorizontal className="h-4 w-4" />
                    </Button>
                  </DropdownMenuTrigger>
                  <DropdownMenuContent align="end">
                    <DropdownMenuItem onClick={(e) => { e.stopPropagation(); handleToggleAdmin(user); }}>
                      {user.is_admin ? (
                        <>
                          <ShieldOff className="mr-2 h-4 w-4" />
                          Remove admin
                        </>
                      ) : (
                        <>
                          <Shield className="mr-2 h-4 w-4" />
                          Make admin
                        </>
                      )}
                    </DropdownMenuItem>
                    <DropdownMenuItem onClick={(e) => { e.stopPropagation(); handleToggleActive(user); }}>
                      {user.is_active ? (
                        <>
                          <UserX className="mr-2 h-4 w-4" />
                          Suspend
                        </>
                      ) : (
                        <>
                          <UserCheck className="mr-2 h-4 w-4" />
                          Activate
                        </>
                      )}
                    </DropdownMenuItem>
                    {user.id !== currentUserId && (
                      <DropdownMenuItem
                        className="text-destructive"
                        onClick={(e) => { e.stopPropagation(); setDeleteTarget(user); }}
                      >
                        <Trash2 className="mr-2 h-4 w-4" />
                        Delete user
                      </DropdownMenuItem>
                    )}
                  </DropdownMenuContent>
                </DropdownMenu>
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>

      <AlertDialog open={!!deleteTarget} onOpenChange={() => setDeleteTarget(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete user?</AlertDialogTitle>
            <AlertDialogDescription>
              This will permanently delete {deleteTarget?.full_name} ({deleteTarget?.email})
              and all their data. This action cannot be undone.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={handleDelete}
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
            >
              Delete
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  );
}

export const UsersTable = memo(UsersTableInner);
