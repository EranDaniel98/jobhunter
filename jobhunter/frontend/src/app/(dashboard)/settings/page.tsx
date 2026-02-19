"use client";

import { useEffect, useState } from "react";
import { useAuth } from "@/providers/auth-provider";
import { PageHeader } from "@/components/shared/page-header";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Separator } from "@/components/ui/separator";
import { toast } from "sonner";
import { Loader2, X } from "lucide-react";

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

      <div className="flex justify-end">
        <Button onClick={handleSave} disabled={loading}>
          {loading && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
          Save changes
        </Button>
      </div>
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
