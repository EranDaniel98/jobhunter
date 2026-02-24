"use client";

import { useAdminUser, useToggleAdmin, useToggleActive, useDeleteUser } from "@/lib/hooks/use-admin";
import { useState } from "react";

import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";
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
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import {
  Shield,
  ShieldOff,
  UserCheck,
  UserX,
  Trash2,
  Loader2,
  Building2,
  Mail,
  Calendar,
  Link2,
} from "lucide-react";
import { toast } from "sonner";

interface UserDetailDrawerProps {
  userId: string | null;
  currentUserId: string;
  onClose: () => void;
}

export function UserDetailDrawer({ userId, currentUserId, onClose }: UserDetailDrawerProps) {
  const { data: user, isLoading } = useAdminUser(userId || "");
  const toggleAdmin = useToggleAdmin();
  const toggleActive = useToggleActive();
  const deleteUser = useDeleteUser();
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);

  const handleToggleAdmin = () => {
    if (!user) return;
    toggleAdmin.mutate(
      { id: user.id, isAdmin: !user.is_admin },
      {
        onSuccess: () => {
          toast.success(user.is_admin ? `Removed admin from ${user.full_name}` : `Made ${user.full_name} admin`);
        },
        onError: () => toast.error("Failed to update admin status"),
      }
    );
  };

  const handleToggleActive = () => {
    if (!user) return;
    toggleActive.mutate(
      { id: user.id, isActive: !user.is_active },
      {
        onSuccess: () => {
          toast.success(user.is_active ? `Suspended ${user.full_name}` : `Activated ${user.full_name}`);
        },
        onError: () => toast.error("Failed to update status"),
      }
    );
  };

  const handleDelete = () => {
    if (!user) return;
    deleteUser.mutate(user.id, {
      onSuccess: () => {
        toast.success(`Deleted ${user.full_name}`);
        setShowDeleteConfirm(false);
        onClose();
      },
      onError: () => toast.error("Failed to delete user"),
    });
  };

  const isSelf = user?.id === currentUserId;

  return (
    <>
      <Sheet open={!!userId} onOpenChange={(open) => !open && onClose()}>
        <SheetContent className="w-[400px] sm:w-[450px] overflow-y-auto">
          <SheetHeader>
            <SheetTitle>User Details</SheetTitle>
          </SheetHeader>

          {isLoading ? (
            <div className="flex items-center justify-center py-12">
              <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
            </div>
          ) : user ? (
            <div className="space-y-6 mt-6">
              {/* Profile info */}
              <div className="space-y-2">
                <h3 className="text-lg font-semibold">{user.full_name}</h3>
                <p className="text-sm text-muted-foreground">{user.email}</p>
                <div className="flex gap-2 flex-wrap">
                  {user.is_admin && (
                    <Badge variant="default" className="gap-1">
                      <Shield className="h-3 w-3" />
                      Admin
                    </Badge>
                  )}
                  <Badge variant={user.is_active ? "secondary" : "destructive"}>
                    {user.is_active ? "Active" : "Suspended"}
                  </Badge>
                </div>
              </div>

              <Separator />

              {/* Details */}
              <div className="space-y-3">
                <div className="flex items-center gap-2 text-sm">
                  <Calendar className="h-4 w-4 text-muted-foreground" />
                  <span className="text-muted-foreground">Joined:</span>
                  <span>{new Date(user.created_at).toLocaleDateString()}</span>
                </div>
                {user.invited_by_email && (
                  <div className="flex items-center gap-2 text-sm">
                    <Link2 className="h-4 w-4 text-muted-foreground" />
                    <span className="text-muted-foreground">Invited by:</span>
                    <span>{user.invited_by_email}</span>
                  </div>
                )}
                {user.invite_code_used && (
                  <div className="flex items-center gap-2 text-sm">
                    <Link2 className="h-4 w-4 text-muted-foreground" />
                    <span className="text-muted-foreground">Code:</span>
                    <code className="text-xs">{user.invite_code_used.slice(0, 12)}...</code>
                  </div>
                )}
              </div>

              <Separator />

              {/* Stats */}
              <div className="grid grid-cols-2 gap-4">
                <div className="rounded-md border p-3 text-center">
                  <Building2 className="h-4 w-4 mx-auto mb-1 text-muted-foreground" />
                  <div className="text-2xl font-bold">{user.companies_count}</div>
                  <p className="text-xs text-muted-foreground">Companies</p>
                </div>
                <div className="rounded-md border p-3 text-center">
                  <Mail className="h-4 w-4 mx-auto mb-1 text-muted-foreground" />
                  <div className="text-2xl font-bold">{user.messages_sent_count}</div>
                  <p className="text-xs text-muted-foreground">Messages Sent</p>
                </div>
              </div>

              <Separator />

              {/* Actions */}
              <div className="space-y-2">
                <Button
                  variant="outline"
                  className="w-full justify-start"
                  onClick={handleToggleAdmin}
                  disabled={toggleAdmin.isPending}
                >
                  {toggleAdmin.isPending ? (
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  ) : user.is_admin ? (
                    <ShieldOff className="mr-2 h-4 w-4" />
                  ) : (
                    <Shield className="mr-2 h-4 w-4" />
                  )}
                  {user.is_admin ? "Remove admin" : "Make admin"}
                </Button>

                <Button
                  variant="outline"
                  className="w-full justify-start"
                  onClick={handleToggleActive}
                  disabled={toggleActive.isPending}
                >
                  {toggleActive.isPending ? (
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  ) : user.is_active ? (
                    <UserX className="mr-2 h-4 w-4" />
                  ) : (
                    <UserCheck className="mr-2 h-4 w-4" />
                  )}
                  {user.is_active ? "Suspend user" : "Activate user"}
                </Button>

                {!isSelf && (
                  <Button
                    variant="destructive"
                    className="w-full justify-start"
                    onClick={() => setShowDeleteConfirm(true)}
                    disabled={deleteUser.isPending}
                  >
                    {deleteUser.isPending ? (
                      <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    ) : (
                      <Trash2 className="mr-2 h-4 w-4" />
                    )}
                    Delete user
                  </Button>
                )}
              </div>
            </div>
          ) : null}
        </SheetContent>
      </Sheet>

      <AlertDialog open={showDeleteConfirm} onOpenChange={setShowDeleteConfirm}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete user?</AlertDialogTitle>
            <AlertDialogDescription>
              This will permanently delete {user?.full_name} ({user?.email}) and
              all their data. This action cannot be undone.
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
