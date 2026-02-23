"use client";

import { useEffect, useState } from "react";
import { useAuth } from "@/providers/auth-provider";
import { useInvites, useCreateInvite } from "@/lib/hooks/use-invites";
import { PageHeader } from "@/components/shared/page-header";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Separator } from "@/components/ui/separator";
import { toast } from "sonner";
import { Checkbox } from "@/components/ui/checkbox";
import { Copy, Loader2, Plus, X } from "lucide-react";

export default function SettingsPage() {
  const { user, updateProfile } = useAuth();
  const [loading, setLoading] = useState(false);
  const [fullName, setFullName] = useState("");
  const [headline, setHeadline] = useState("");
  const [location, setLocation] = useState("");
  const [targetRoles, setTargetRoles] = useState<string[]>([]);
  const [targetIndustries, setTargetIndustries] = useState<string[]>([]);
  const [targetLocations, setTargetLocations] = useState<string[]>([]);
  const [salaryMin, setSalaryMin] = useState("");
  const [salaryMax, setSalaryMax] = useState("");

  // Tag input states
  const [roleInput, setRoleInput] = useState("");
  const [industryInput, setIndustryInput] = useState("");
  const [locationInput, setLocationInput] = useState("");

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
    } catch {
      toast.error("Failed to save settings");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="space-y-6">
      <PageHeader title="Settings" description="Manage your profile and job search preferences" />

      <Card>
        <CardHeader>
          <CardTitle>Profile</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid gap-4 sm:grid-cols-2">
            <div className="space-y-2">
              <Label>Full name</Label>
              <Input value={fullName} onChange={(e) => setFullName(e.target.value)} />
            </div>
            <div className="space-y-2">
              <Label>Email</Label>
              <Input value={user?.email || ""} disabled />
            </div>
          </div>
          <div className="space-y-2">
            <Label>Headline</Label>
            <Input
              value={headline}
              onChange={(e) => setHeadline(e.target.value)}
              placeholder="e.g. Senior Software Engineer"
            />
          </div>
          <div className="space-y-2">
            <Label>Location</Label>
            <Input
              value={location}
              onChange={(e) => setLocation(e.target.value)}
              placeholder="e.g. San Francisco, CA"
            />
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Target preferences</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
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
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Salary range</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid gap-4 sm:grid-cols-2">
            <div className="space-y-2">
              <Label>Minimum ($)</Label>
              <Input
                type="number"
                value={salaryMin}
                onChange={(e) => setSalaryMin(e.target.value)}
                placeholder="80000"
              />
            </div>
            <div className="space-y-2">
              <Label>Maximum ($)</Label>
              <Input
                type="number"
                value={salaryMax}
                onChange={(e) => setSalaryMax(e.target.value)}
                placeholder="150000"
              />
            </div>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Notifications</CardTitle>
        </CardHeader>
        <CardContent>
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
                } catch {
                  toast.error("Failed to update preference");
                }
              }}
            />
            <Label htmlFor="email-notifications" className="cursor-pointer">
              Receive platform emails (announcements, tips)
            </Label>
          </div>
        </CardContent>
      </Card>

      <div className="flex justify-end">
        <Button onClick={handleSave} disabled={loading}>
          {loading && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
          Save changes
        </Button>
      </div>

      <InviteSection />
    </div>
  );
}

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
              <button onClick={() => onRemove(i)} className="text-muted-foreground hover:text-foreground">
                <X className="h-3 w-3" />
              </button>
            </span>
          ))}
        </div>
      )}
    </div>
  );
}

type InviteFilter = "all" | "active" | "used" | "expired";

function InviteSection() {
  const { data: invites } = useInvites();
  const createInvite = useCreateInvite();
  const [filter, setFilter] = useState<InviteFilter>("all");

  async function handleGenerate() {
    try {
      const result = await createInvite.mutateAsync();
      await navigator.clipboard.writeText(result.invite_url);
      toast.success("Invite link copied to clipboard");
    } catch {
      toast.error("Failed to generate invite");
    }
  }

  function copyInviteUrl(code: string) {
    const url = `${window.location.origin}/register?invite=${code}`;
    navigator.clipboard.writeText(url);
    toast.success("Link copied");
  }

  function getStatus(invite: { is_used: boolean; expires_at: string }) {
    if (invite.is_used) return { label: "Used", variant: "secondary" as const, key: "used" as const };
    if (new Date(invite.expires_at) < new Date()) return { label: "Expired", variant: "destructive" as const, key: "expired" as const };
    return { label: "Active", variant: "default" as const, key: "active" as const };
  }

  const filtered = invites?.filter((invite) => {
    if (filter === "all") return true;
    return getStatus(invite).key === filter;
  });

  const counts = invites?.reduce(
    (acc, invite) => {
      acc[getStatus(invite).key]++;
      return acc;
    },
    { active: 0, used: 0, expired: 0 } as Record<string, number>
  );

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between">
        <CardTitle>Invite people</CardTitle>
        <Button
          size="sm"
          onClick={handleGenerate}
          disabled={createInvite.isPending}
        >
          {createInvite.isPending ? (
            <Loader2 className="mr-2 h-4 w-4 animate-spin" />
          ) : (
            <Plus className="mr-2 h-4 w-4" />
          )}
          Generate invite link
        </Button>
      </CardHeader>
      <CardContent className="space-y-3">
        {invites && invites.length > 0 && (
          <div className="flex gap-2">
            {(["all", "active", "used", "expired"] as InviteFilter[]).map((f) => (
              <Button
                key={f}
                variant={filter === f ? "default" : "outline"}
                size="sm"
                onClick={() => setFilter(f)}
              >
                {f.charAt(0).toUpperCase() + f.slice(1)}
                {f !== "all" && counts && (
                  <span className="ml-1.5 text-xs opacity-70">
                    {counts[f] ?? 0}
                  </span>
                )}
              </Button>
            ))}
          </div>
        )}

        {filtered && filtered.length > 0 ? (
          <div className="max-h-[320px] overflow-y-auto space-y-3 pr-1">
            {filtered.map((invite) => {
              const status = getStatus(invite);
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
      </CardContent>
    </Card>
  );
}
