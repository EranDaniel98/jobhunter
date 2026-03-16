"use client";

import { useEffect, useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { changePasswordSchema, type ChangePasswordFormData } from "@/lib/schemas/auth";
import { useRouter } from "next/navigation";
import { useAuth } from "@/providers/auth-provider";
import { useInvites, useCreateInvite } from "@/lib/hooks/use-invites";
import { PageHeader } from "@/components/shared/page-header";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Separator } from "@/components/ui/separator";
import { Checkbox } from "@/components/ui/checkbox";
import { toast } from "sonner";
import { toastError } from "@/lib/api/error-utils";
import { changePassword } from "@/lib/api/auth";
import type { PlanTier } from "@/lib/types";
import { cn } from "@/lib/utils";
import {
  User, Shield, Target, CreditCard, UserPlus,
  Copy, Loader2, Plus, X, Eye, EyeOff, RotateCcw,
} from "lucide-react";

const TABS = [
  { id: "profile", label: "Profile", icon: User },
  { id: "security", label: "Security", icon: Shield },
  { id: "preferences", label: "Preferences", icon: Target },
  { id: "billing", label: "Plan & Billing", icon: CreditCard },
  { id: "invites", label: "Invites", icon: UserPlus },
] as const;

type TabId = (typeof TABS)[number]["id"];

const PLAN_DISPLAY: Record<PlanTier, { name: string; className: string }> = {
  free: { name: "Free Plan", className: "" },
  explorer: { name: "Explorer", className: "bg-secondary text-secondary-foreground" },
  hunter: { name: "Hunter", className: "bg-primary/15 text-primary" },
};

type InviteFilter = "all" | "active" | "used" | "expired";

export default function SettingsPage() {
  const { user, updateProfile, resetTour } = useAuth();
  const router = useRouter();
  const [activeTab, setActiveTab] = useState<TabId>("profile");
  const [loading, setLoading] = useState(false);

  // Profile state
  const [fullName, setFullName] = useState("");
  const [headline, setHeadline] = useState("");
  const [location, setLocation] = useState("");

  // Preferences state
  const [targetRoles, setTargetRoles] = useState<string[]>([]);
  const [targetIndustries, setTargetIndustries] = useState<string[]>([]);
  const [targetLocations, setTargetLocations] = useState<string[]>([]);
  const [salaryMin, setSalaryMin] = useState("");
  const [salaryMax, setSalaryMax] = useState("");

  // Tag input states
  const [roleInput, setRoleInput] = useState("");
  const [industryInput, setIndustryInput] = useState("");
  const [locationInput, setLocationInput] = useState("");

  // Security state
  const [showCurrent, setShowCurrent] = useState(false);
  const [showNew, setShowNew] = useState(false);
  const pwForm = useForm<ChangePasswordFormData>({
    resolver: zodResolver(changePasswordSchema),
    defaultValues: { currentPassword: "", newPassword: "", confirmPassword: "" },
  });

  // Invites state
  const { data: invites } = useInvites();
  const createInvite = useCreateInvite();
  const [inviteFilter, setInviteFilter] = useState<InviteFilter>("all");

  useEffect(() => {
    if (user) {
      setFullName(user.full_name || "");
      setHeadline(user.headline || "");
      setLocation(user.location || "");
      setTargetRoles(user.target_roles || []);
      setTargetIndustries(user.target_industries || []);
      setTargetLocations(user.target_locations || []);
      setSalaryMin(user.salary_min?.toString() || "");
      setSalaryMax(user.salary_max?.toString() || "");
    }
  }, [user]);

  const isDirty = user ? (
    fullName !== (user.full_name || "") ||
    headline !== (user.headline || "") ||
    location !== (user.location || "") ||
    JSON.stringify(targetRoles) !== JSON.stringify(user.target_roles || []) ||
    JSON.stringify(targetIndustries) !== JSON.stringify(user.target_industries || []) ||
    JSON.stringify(targetLocations) !== JSON.stringify(user.target_locations || []) ||
    salaryMin !== (user.salary_min?.toString() || "") ||
    salaryMax !== (user.salary_max?.toString() || "")
  ) : false;

  function resetForm() {
    if (user) {
      setFullName(user.full_name || "");
      setHeadline(user.headline || "");
      setLocation(user.location || "");
      setTargetRoles(user.target_roles || []);
      setTargetIndustries(user.target_industries || []);
      setTargetLocations(user.target_locations || []);
      setSalaryMin(user.salary_min?.toString() || "");
      setSalaryMax(user.salary_max?.toString() || "");
    }
  }

  function addTag(
    value: string,
    list: string[],
    setter: (v: string[]) => void,
    inputSetter: (v: string) => void
  ) {
    const trimmed = value.trim();
    if (trimmed && !list.includes(trimmed)) {
      setter([...list, trimmed]);
    }
    inputSetter("");
  }

  function removeTag(index: number, list: string[], setter: (v: string[]) => void) {
    setter(list.filter((_, i) => i !== index));
  }

  async function handleSave() {
    setLoading(true);
    try {
      await updateProfile({
        full_name: fullName,
        headline: headline || undefined,
        location: location || undefined,
        target_roles: targetRoles.length ? targetRoles : undefined,
        target_industries: targetIndustries.length ? targetIndustries : undefined,
        target_locations: targetLocations.length ? targetLocations : undefined,
        salary_min: salaryMin ? parseInt(salaryMin) : null,
        salary_max: salaryMax ? parseInt(salaryMax) : null,
      });
      toast.success("Settings saved");
    } catch (err) {
      toastError(err, "Failed to save settings");
    } finally {
      setLoading(false);
    }
  }

  async function handleChangePassword(data: ChangePasswordFormData) {
    try {
      await changePassword(data.currentPassword, data.newPassword);
      toast.success("Password changed successfully");
      pwForm.reset();
    } catch (err) {
      toastError(err, "Failed to change password");
    }
  }

  async function handleGenerateInvite() {
    try {
      const result = await createInvite.mutateAsync();
      try {
        await navigator.clipboard.writeText(result.invite_url);
        toast.success("Invite link copied to clipboard");
      } catch {
        toast.success("Invite created (copy failed — use the link below)");
      }
    } catch (err) {
      toastError(err, "Failed to generate invite");
    }
  }

  async function copyInviteUrl(code: string) {
    const url = `${window.location.origin}/register?invite=${code}`;
    try {
      await navigator.clipboard.writeText(url);
      toast.success("Link copied");
    } catch {
      toast.error("Failed to copy link");
    }
  }

  function getInviteStatus(invite: { is_used: boolean; expires_at: string }) {
    if (invite.is_used) return { label: "Used", variant: "secondary" as const, key: "used" as const };
    if (new Date(invite.expires_at) < new Date()) return { label: "Expired", variant: "destructive" as const, key: "expired" as const };
    return { label: "Active", variant: "default" as const, key: "active" as const };
  }

  const filteredInvites = invites?.filter((invite) => {
    if (inviteFilter === "all") return true;
    return getInviteStatus(invite).key === inviteFilter;
  });

  const inviteCounts = invites?.reduce(
    (acc, invite) => {
      acc[getInviteStatus(invite).key]++;
      return acc;
    },
    { active: 0, used: 0, expired: 0 } as Record<string, number>
  );

  const plan = PLAN_DISPLAY[user?.plan_tier || "free"] || PLAN_DISPLAY.free;

  return (
    <div className="space-y-6">
      <PageHeader title="Settings" description="Manage your profile and job search preferences" dataTour="page-header" />

      <div className="flex flex-col md:flex-row gap-6 min-h-[600px]">
        {/* Sidebar tabs */}
        <nav className="shrink-0">
          {/* Mobile: horizontal scroll */}
          <div className="flex gap-1 overflow-x-auto md:hidden pb-2">
            {TABS.map((tab) => {
              const Icon = tab.icon;
              return (
                <button
                  key={tab.id}
                  onClick={() => setActiveTab(tab.id)}
                  className={cn(
                    "flex items-center gap-2 rounded-lg px-3 py-2 text-sm whitespace-nowrap transition-colors",
                    activeTab === tab.id
                      ? "bg-primary/10 text-primary font-medium"
                      : "text-muted-foreground hover:text-foreground hover:bg-muted"
                  )}
                >
                  <Icon className="h-4 w-4" />
                  {tab.label}
                </button>
              );
            })}
          </div>
          {/* Desktop: vertical list */}
          <div className="hidden md:flex md:flex-col md:w-48 gap-1">
            {TABS.map((tab) => {
              const Icon = tab.icon;
              return (
                <button
                  key={tab.id}
                  onClick={() => setActiveTab(tab.id)}
                  className={cn(
                    "flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm transition-colors text-left",
                    activeTab === tab.id
                      ? "bg-primary/10 text-primary font-medium"
                      : "text-muted-foreground hover:text-foreground hover:bg-muted"
                  )}
                >
                  <Icon className="h-4 w-4 shrink-0" />
                  {tab.label}
                </button>
              );
            })}
          </div>
        </nav>

        {/* Content area */}
        <div className="flex-1 min-w-0">
          <Card>
            <CardContent className="p-6">

              {/* ===== Profile Section ===== */}
              {activeTab === "profile" && (
                <div className="space-y-6">
                  <div>
                    <h2 className="text-lg font-semibold">Profile</h2>
                    <p className="text-sm text-muted-foreground">Your personal information</p>
                  </div>
                  <Separator />
                  <div className="grid gap-4 sm:grid-cols-2 max-w-2xl">
                    <div className="space-y-2">
                      <Label>Full name</Label>
                      <Input value={fullName} onChange={(e) => setFullName(e.target.value)} />
                    </div>
                    <div className="space-y-2">
                      <Label>Email</Label>
                      <Input value={user?.email || ""} disabled />
                    </div>
                  </div>
                  <div className="space-y-2 max-w-2xl">
                    <Label>Headline</Label>
                    <Input
                      value={headline}
                      onChange={(e) => setHeadline(e.target.value)}
                      placeholder="e.g. Senior Software Engineer"
                    />
                  </div>
                  <div className="space-y-2 max-w-2xl">
                    <Label>Location</Label>
                    <Input
                      value={location}
                      onChange={(e) => setLocation(e.target.value)}
                      placeholder="e.g. San Francisco, CA"
                    />
                  </div>
                </div>
              )}

              {/* ===== Security Section ===== */}
              {activeTab === "security" && (
                <div className="space-y-6">
                  <div>
                    <h2 className="text-lg font-semibold">Security</h2>
                    <p className="text-sm text-muted-foreground">Manage your password</p>
                  </div>
                  <Separator />
                  <form onSubmit={pwForm.handleSubmit(handleChangePassword)} className="space-y-4 max-w-md">
                    <div className="space-y-2">
                      <Label htmlFor="currentPassword">Current password</Label>
                      <div className="relative">
                        <Input
                          id="currentPassword"
                          type={showCurrent ? "text" : "password"}
                          {...pwForm.register("currentPassword")}
                          aria-invalid={!!pwForm.formState.errors.currentPassword}
                          aria-describedby={pwForm.formState.errors.currentPassword ? "current-pw-error" : undefined}
                        />
                        <Button
                          type="button"
                          variant="ghost"
                          size="icon"
                          className="absolute right-0 top-0 h-full px-3"
                          onClick={() => setShowCurrent(!showCurrent)}
                          aria-label={showCurrent ? "Hide password" : "Show password"}
                        >
                          {showCurrent ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                        </Button>
                      </div>
                      {pwForm.formState.errors.currentPassword && (
                        <p id="current-pw-error" className="text-sm text-destructive">
                          {pwForm.formState.errors.currentPassword.message}
                        </p>
                      )}
                    </div>
                    <div className="space-y-2">
                      <Label htmlFor="newPassword">New password</Label>
                      <div className="relative">
                        <Input
                          id="newPassword"
                          type={showNew ? "text" : "password"}
                          {...pwForm.register("newPassword")}
                          aria-invalid={!!pwForm.formState.errors.newPassword}
                          aria-describedby={pwForm.formState.errors.newPassword ? "new-pw-error" : undefined}
                        />
                        <Button
                          type="button"
                          variant="ghost"
                          size="icon"
                          className="absolute right-0 top-0 h-full px-3"
                          onClick={() => setShowNew(!showNew)}
                          aria-label={showNew ? "Hide password" : "Show password"}
                        >
                          {showNew ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                        </Button>
                      </div>
                      {pwForm.formState.errors.newPassword && (
                        <p id="new-pw-error" className="text-sm text-destructive">
                          {pwForm.formState.errors.newPassword.message}
                        </p>
                      )}
                    </div>
                    <div className="space-y-2">
                      <Label htmlFor="confirmPassword">Confirm new password</Label>
                      <Input
                        id="confirmPassword"
                        type="password"
                        {...pwForm.register("confirmPassword")}
                        aria-invalid={!!pwForm.formState.errors.confirmPassword}
                        aria-describedby={pwForm.formState.errors.confirmPassword ? "confirm-pw-error" : undefined}
                      />
                      {pwForm.formState.errors.confirmPassword && (
                        <p id="confirm-pw-error" className="text-sm text-destructive">
                          {pwForm.formState.errors.confirmPassword.message}
                        </p>
                      )}
                    </div>
                    <Button type="submit" disabled={pwForm.formState.isSubmitting}>
                      {pwForm.formState.isSubmitting && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                      Change password
                    </Button>
                  </form>
                </div>
              )}

              {/* ===== Preferences Section ===== */}
              {activeTab === "preferences" && (
                <div className="space-y-6">
                  <div>
                    <h2 className="text-lg font-semibold">Preferences</h2>
                    <p className="text-sm text-muted-foreground">Configure your job search targets and notifications</p>
                  </div>
                  <Separator />

                  <TagInput
                    label="Target roles"
                    tags={targetRoles}
                    value={roleInput}
                    onChange={setRoleInput}
                    onAdd={() => addTag(roleInput, targetRoles, setTargetRoles, setRoleInput)}
                    onRemove={(i) => removeTag(i, targetRoles, setTargetRoles)}
                    placeholder="e.g. Software Engineer"
                  />
                  <Separator />
                  <TagInput
                    label="Target industries"
                    tags={targetIndustries}
                    value={industryInput}
                    onChange={setIndustryInput}
                    onAdd={() => addTag(industryInput, targetIndustries, setTargetIndustries, setIndustryInput)}
                    onRemove={(i) => removeTag(i, targetIndustries, setTargetIndustries)}
                    placeholder="e.g. Fintech"
                  />
                  <Separator />
                  <TagInput
                    label="Target locations"
                    tags={targetLocations}
                    value={locationInput}
                    onChange={setLocationInput}
                    onAdd={() => addTag(locationInput, targetLocations, setTargetLocations, setLocationInput)}
                    onRemove={(i) => removeTag(i, targetLocations, setTargetLocations)}
                    placeholder="e.g. Remote, New York"
                  />

                  <Separator />

                  {/* Salary range */}
                  <div className="space-y-2">
                    <Label className="text-sm font-medium">Salary range</Label>
                    <div className="grid gap-4 sm:grid-cols-2 max-w-md">
                      <div className="space-y-2">
                        <Label className="text-xs text-muted-foreground">Minimum ($)</Label>
                        <Input
                          type="number"
                          value={salaryMin}
                          onChange={(e) => setSalaryMin(e.target.value)}
                          placeholder="80000"
                        />
                      </div>
                      <div className="space-y-2">
                        <Label className="text-xs text-muted-foreground">Maximum ($)</Label>
                        <Input
                          type="number"
                          value={salaryMax}
                          onChange={(e) => setSalaryMax(e.target.value)}
                          placeholder="150000"
                        />
                      </div>
                    </div>
                  </div>

                  <Separator />

                  {/* Notifications */}
                  <div className="space-y-2">
                    <Label className="text-sm font-medium">Notifications</Label>
                    <div className="flex items-center gap-3">
                      <Checkbox
                        id="email-notifications"
                        checked={
                          (user?.preferences as Record<string, unknown> | null)?.email_notifications !== false
                        }
                        onCheckedChange={async (checked) => {
                          try {
                            await updateProfile({
                              preferences: {
                                ...((user?.preferences as Record<string, unknown>) || {}),
                                email_notifications: !!checked,
                              },
                            });
                            toast.success("Notification preference saved");
                          } catch (err) {
                            toastError(err, "Failed to update preference");
                          }
                        }}
                      />
                      <Label htmlFor="email-notifications" className="cursor-pointer">
                        Receive platform emails (announcements, tips)
                      </Label>
                    </div>
                  </div>
                </div>
              )}

              {/* ===== Plan & Billing Section ===== */}
              {activeTab === "billing" && (
                <div className="space-y-6">
                  <div>
                    <h2 className="text-lg font-semibold">Plan & Billing</h2>
                    <p className="text-sm text-muted-foreground">Manage your subscription</p>
                  </div>
                  <Separator />
                  <div className="space-y-3">
                    <div className="flex items-center gap-3">
                      <span className="text-sm text-muted-foreground">Current plan:</span>
                      {plan.className ? (
                        <Badge className={plan.className}>{plan.name}</Badge>
                      ) : (
                        <Badge variant="secondary">{plan.name}</Badge>
                      )}
                      {user?.is_admin && (
                        <Badge className="bg-amber-500/15 text-amber-600">Admin</Badge>
                      )}
                    </div>
                    <div className="flex items-center gap-3">
                      <a href="/plans">
                        <Button variant="outline" size="sm">
                          View Plans
                        </Button>
                      </a>
                    </div>
                    <p className="text-xs text-muted-foreground">
                      Paid plans coming soon
                    </p>
                  </div>
                </div>
              )}

              {/* ===== Invites Section ===== */}
              {activeTab === "invites" && (
                <div className="space-y-6">
                  <div className="flex items-center justify-between">
                    <div>
                      <h2 className="text-lg font-semibold">Invites</h2>
                      <p className="text-sm text-muted-foreground">Generate invite links to share with others</p>
                    </div>
                    <Button
                      size="sm"
                      onClick={handleGenerateInvite}
                      disabled={createInvite.isPending}
                    >
                      {createInvite.isPending ? (
                        <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                      ) : (
                        <Plus className="mr-2 h-4 w-4" />
                      )}
                      Generate invite link
                    </Button>
                  </div>
                  <Separator />

                  {invites && invites.length > 0 && (
                    <div className="flex gap-2">
                      {(["all", "active", "used", "expired"] as InviteFilter[]).map((f) => (
                        <Button
                          key={f}
                          variant={inviteFilter === f ? "default" : "outline"}
                          size="sm"
                          onClick={() => setInviteFilter(f)}
                        >
                          {f.charAt(0).toUpperCase() + f.slice(1)}
                          {f !== "all" && inviteCounts && (
                            <span className="ml-1.5 text-xs opacity-70">
                              {inviteCounts[f] ?? 0}
                            </span>
                          )}
                        </Button>
                      ))}
                    </div>
                  )}

                  {filteredInvites && filteredInvites.length > 0 ? (
                    <div className="max-h-[320px] overflow-y-auto space-y-3 pr-1">
                      {filteredInvites.map((invite) => {
                        const status = getInviteStatus(invite);
                        return (
                          <div
                            key={invite.id}
                            className="flex items-center justify-between rounded-md border px-4 py-3"
                          >
                            <div className="flex items-center gap-3 min-w-0">
                              <Badge variant={status.variant}>{status.label}</Badge>
                              <code className="text-xs text-muted-foreground truncate">
                                {invite.code.slice(0, 16)}...
                              </code>
                              {invite.used_by_email && (
                                <span className="text-xs text-muted-foreground">
                                  {invite.used_by_email}
                                </span>
                              )}
                            </div>
                            <Button
                              variant="ghost"
                              size="icon"
                              onClick={() => copyInviteUrl(invite.code)}
                              title="Copy invite link"
                              aria-label="Copy invite link"
                            >
                              <Copy className="h-4 w-4" />
                            </Button>
                          </div>
                        );
                      })}
                    </div>
                  ) : (
                    <p className="text-sm text-muted-foreground">
                      {invites && invites.length > 0
                        ? "No invites match this filter."
                        : "No invites yet. Generate one to share with others."}
                    </p>
                  )}
                </div>
              )}

            </CardContent>
          </Card>
        </div>
      </div>

      {/* Guided Tour */}
      <Card>
        <CardHeader>
          <CardTitle>Guided Tour</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm">Replay the dashboard guided tour</p>
              <p className="text-xs text-muted-foreground">
                Walk through each feature again with spotlight explanations.
              </p>
            </div>
            <Button
              variant="outline"
              size="sm"
              onClick={() => {
                resetTour();
                router.push("/dashboard");
              }}
            >
              <RotateCcw className="mr-1.5 h-3.5 w-3.5" />
              Replay tour
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* Sticky save bar (profile/preferences changes) */}
      {isDirty && (
        <div className="fixed bottom-0 left-0 right-0 z-40 border-t bg-card p-3 shadow-lg lg:left-64">
          <div className="flex items-center justify-end gap-3 max-w-5xl mx-auto">
            <Button variant="ghost" onClick={resetForm}>Discard</Button>
            <Button onClick={handleSave} disabled={loading}>
              {loading && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              Save changes
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}

/* ===== Tag Input Helper ===== */

function TagInput({
  label,
  tags,
  value,
  onChange,
  onAdd,
  onRemove,
  placeholder,
}: {
  label: string;
  tags: string[];
  value: string;
  onChange: (v: string) => void;
  onAdd: () => void;
  onRemove: (i: number) => void;
  placeholder: string;
}) {
  return (
    <div className="space-y-2">
      <Label>{label}</Label>
      <div className="flex gap-2">
        <Input
          value={value}
          onChange={(e) => onChange(e.target.value)}
          placeholder={placeholder}
          onKeyDown={(e) => {
            if (e.key === "Enter") {
              e.preventDefault();
              onAdd();
            }
          }}
        />
        <Button type="button" variant="secondary" onClick={onAdd}>
          Add
        </Button>
      </div>
      {tags.length > 0 && (
        <div className="flex flex-wrap gap-2">
          {tags.map((tag, i) => (
            <span
              key={i}
              className="inline-flex items-center gap-1 rounded-md bg-secondary px-2.5 py-1 text-sm"
            >
              {tag}
              <button onClick={() => onRemove(i)} className="text-muted-foreground hover:text-foreground" aria-label={`Remove ${tag}`}>
                <X className="h-3 w-3" />
              </button>
            </span>
          ))}
        </div>
      )}
    </div>
  );
}
