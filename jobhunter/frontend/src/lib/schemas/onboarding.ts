import { z } from "zod";

export const onboardingProfileSchema = z.object({
  headline: z.string().max(500).optional().or(z.literal("")),
  location: z.string().max(255).optional().or(z.literal("")),
  target_roles: z.array(z.string()).max(10).optional(),
  target_industries: z.array(z.string()).max(10).optional(),
  target_locations: z.array(z.string()).max(10).optional(),
  salary_min: z.coerce.number().nonnegative().optional().or(z.literal("")),
  salary_max: z.coerce.number().nonnegative().optional().or(z.literal("")),
});

export type OnboardingProfileFormData = z.input<typeof onboardingProfileSchema>;
