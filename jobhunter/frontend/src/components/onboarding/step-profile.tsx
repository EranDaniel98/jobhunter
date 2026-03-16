"use client";

import { useImperativeHandle, forwardRef, useRef } from "react";
import { useForm, Controller } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { useAuth } from "@/providers/auth-provider";
import { onboardingProfileSchema, type OnboardingProfileFormData } from "@/lib/schemas/onboarding";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { TagInput } from "@/components/onboarding/tag-input";
import { toast } from "sonner";

export interface StepProfileHandle {
  submit: () => Promise<boolean>;
}

export const StepProfile = forwardRef<StepProfileHandle, { onComplete: () => void }>(
  function StepProfile({ onComplete }, ref) {
    const { user, updateProfile } = useAuth();
    const formRef = useRef<HTMLFormElement>(null);

    const {
      register,
      handleSubmit,
      control,
      formState: { errors, isSubmitting },
    } = useForm<OnboardingProfileFormData>({
      resolver: zodResolver(onboardingProfileSchema),
      defaultValues: {
        headline: user?.headline || "",
        location: user?.location || "",
        target_roles: user?.target_roles || [],
        target_industries: user?.target_industries || [],
        target_locations: user?.target_locations || [],
        salary_min: user?.salary_min ?? ("" as unknown as undefined),
        salary_max: user?.salary_max ?? ("" as unknown as undefined),
      },
    });

    useImperativeHandle(ref, () => ({
      submit: async () => {
        let success = false;
        await handleSubmit(async (data) => {
          try {
            const updates: Record<string, unknown> = {};
            if (data.headline) updates.headline = data.headline;
            if (data.location) updates.location = data.location;
            if (data.target_roles?.length) updates.target_roles = data.target_roles;
            if (data.target_industries?.length) updates.target_industries = data.target_industries;
            if (data.target_locations?.length) updates.target_locations = data.target_locations;
            if (data.salary_min && data.salary_min !== "") updates.salary_min = Number(data.salary_min);
            if (data.salary_max && data.salary_max !== "") updates.salary_max = Number(data.salary_max);

            if (Object.keys(updates).length > 0) {
              await updateProfile(updates);
            }
            success = true;
            onComplete();
          } catch (err: unknown) {
            const message =
              (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ||
              "Failed to save profile";
            toast.error(message);
          }
        })();
        return success;
      },
    }));

    return (
      <div className="space-y-6">
        <div>
          <h2 className="text-2xl font-bold">Set up your profile</h2>
          <p className="mt-1 text-muted-foreground">
            Help us understand your career goals. All fields are optional — you can update them later in Settings.
          </p>
        </div>

        <form ref={formRef} className="space-y-5">
          {/* Headline */}
          <div className="space-y-2">
            <Label htmlFor="headline">Professional headline</Label>
            <Input id="headline" placeholder="e.g. Senior Backend Developer" {...register("headline")} />
            <p className="text-xs text-muted-foreground">
              Appears on outreach messages — helps recipients understand who you are at a glance.
            </p>
          </div>

          {/* Location */}
          <div className="space-y-2">
            <Label htmlFor="location">Location</Label>
            <Input id="location" placeholder="e.g. Tel Aviv, Israel" {...register("location")} />
            <p className="text-xs text-muted-foreground">
              Helps us find companies and roles in your area, or filter for remote-friendly positions.
            </p>
          </div>

          {/* Target Roles */}
          <div className="space-y-2">
            <Label>Target roles</Label>
            <Controller
              name="target_roles"
              control={control}
              render={({ field }) => (
                <TagInput
                  value={field.value || []}
                  onChange={field.onChange}
                  placeholder="e.g. Backend Developer, Data Engineer"
                />
              )}
            />
            <p className="text-xs text-muted-foreground">
              What roles are you looking for? We use these to match you with relevant job postings and companies.
            </p>
          </div>

          {/* Target Industries */}
          <div className="space-y-2">
            <Label>Target industries</Label>
            <Controller
              name="target_industries"
              control={control}
              render={({ field }) => (
                <TagInput
                  value={field.value || []}
                  onChange={field.onChange}
                  placeholder="e.g. FinTech, HealthTech, SaaS"
                />
              )}
            />
            <p className="text-xs text-muted-foreground">
              Which industries interest you? Narrows company discovery to sectors you care about.
            </p>
          </div>

          {/* Target Locations */}
          <div className="space-y-2">
            <Label>Preferred work locations</Label>
            <Controller
              name="target_locations"
              control={control}
              render={({ field }) => (
                <TagInput
                  value={field.value || []}
                  onChange={field.onChange}
                  placeholder="e.g. Tel Aviv, Remote, London"
                />
              )}
            />
            <p className="text-xs text-muted-foreground">
              Where would you like to work? Filters opportunities by geography.
            </p>
          </div>

          {/* Salary Range */}
          <div className="space-y-2">
            <Label>Salary range (annual)</Label>
            <div className="grid grid-cols-2 gap-3">
              <Input
                type="number"
                placeholder="Min"
                {...register("salary_min")}
              />
              <Input
                type="number"
                placeholder="Max"
                {...register("salary_max")}
              />
            </div>
            <p className="text-xs text-muted-foreground">
              Your expected salary range — used to match positions within your expectations. Never shared externally.
            </p>
          </div>
        </form>
      </div>
    );
  }
);
