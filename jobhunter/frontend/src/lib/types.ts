// Auth
export interface TokenPair {
  access_token: string;
  refresh_token: string;
  token_type: string;
}

export interface CandidateResponse {
  id: string;
  email: string;
  full_name: string;
  headline: string | null;
  location: string | null;
  target_roles: string[] | null;
  target_industries: string[] | null;
  target_locations: string[] | null;
  salary_min: number | null;
  salary_max: number | null;
  is_admin: boolean;
  email_verified: boolean;
  preferences: Record<string, unknown> | null;
}

export interface CandidateUpdate {
  full_name?: string;
  headline?: string;
  location?: string;
  target_roles?: string[];
  target_industries?: string[];
  target_locations?: string[];
  salary_min?: number | null;
  salary_max?: number | null;
  preferences?: Record<string, unknown>;
}

// Resume & DNA
export interface ResumeUploadResponse {
  id: string;
  file_path: string;
  is_primary: boolean;
  parsed_data: Record<string, unknown> | null;
}

export interface SkillResponse {
  id: string;
  name: string;
  category: string;
  proficiency: string | null;
  years_experience: number | null;
  evidence: string | null;
}

export interface CandidateDNAResponse {
  id: string;
  experience_summary: string | null;
  strengths: string[] | null;
  gaps: string[] | null;
  career_stage: string | null;
  transferable_skills: Record<string, unknown> | null;
  skills: SkillResponse[];
}

// Companies
export interface CompanyResponse {
  id: string;
  name: string;
  domain: string;
  industry: string | null;
  size_range: string | null;
  location_hq: string | null;
  description: string | null;
  tech_stack: string[] | null;
  funding_stage: string | null;
  fit_score: number | null;
  status: string;
  research_status: string;
}

export interface CompanyListResponse {
  companies: CompanyResponse[];
  total: number;
}

export interface CompanyDossierResponse {
  id: string;
  culture_summary: string | null;
  culture_score: number | null;
  red_flags: string[] | null;
  interview_format: string | null;
  interview_questions: string[] | null;
  compensation_data: Record<string, unknown> | null;
  key_people: Record<string, unknown>[] | null;
  why_hire_me: string | null;
  resume_bullets: string[] | null;
  recent_news: Record<string, unknown>[] | null;
}

// Contacts
export interface ContactResponse {
  id: string;
  company_id: string;
  full_name: string;
  email: string | null;
  email_verified: boolean;
  email_confidence: number | null;
  title: string | null;
  role_type: string | null;
  is_decision_maker: boolean;
  outreach_priority: number;
}

// Outreach
export interface OutreachMessageResponse {
  id: string;
  contact_id: string;
  candidate_id: string;
  channel: string;
  message_type: string;
  subject: string | null;
  body: string;
  personalization_data: Record<string, unknown> | null;
  variant: string | null;
  status: string;
  sent_at: string | null;
  opened_at: string | null;
  replied_at: string | null;
}

// Analytics
export interface FunnelResponse {
  drafted: number;
  sent: number;
  delivered: number;
  opened: number;
  replied: number;
  bounced: number;
}

export interface OutreachStatsResponse {
  total_sent: number;
  total_opened: number;
  total_replied: number;
  open_rate: number;
  reply_rate: number;
  by_channel: Record<string, unknown>;
}

export interface PipelineStatsResponse {
  suggested: number;
  approved: number;
  rejected: number;
  researched: number;
  contacted: number;
}

// Admin
export interface SystemOverview {
  total_users: number;
  total_companies: number;
  total_messages_sent: number;
  total_contacts: number;
  total_invites_used: number;
  active_users_7d: number;
  active_users_30d: number;
}

export interface AdminUser {
  id: string;
  email: string;
  full_name: string;
  is_admin: boolean;
  created_at: string;
  companies_count: number;
  messages_sent_count: number;
  is_active: boolean;
}

export interface AdminUserList {
  users: AdminUser[];
  total: number;
}

export interface AdminUserDetail extends AdminUser {
  invited_by_email: string | null;
  invite_code_used: string | null;
  recent_activity: Record<string, unknown>[];
}

export interface RegistrationTrend {
  date: string;
  count: number;
}

export interface InviteChainItem {
  inviter_email: string;
  inviter_name: string;
  invitee_email: string | null;
  invitee_name: string | null;
  code: string;
  used_at: string | null;
}

export interface TopUserItem {
  email: string;
  full_name: string;
  metric_value: number;
  metric_name: string;
}

export interface ActivityFeedItem {
  id: string;
  user_email: string;
  user_name: string;
  event_type: string;
  entity_type: string | null;
  details: Record<string, unknown> | null;
  occurred_at: string;
}

export interface AuditLogItem {
  id: string;
  admin_email: string | null;
  admin_name: string | null;
  action: string;
  target_email: string | null;
  target_name: string | null;
  details: Record<string, unknown> | null;
  created_at: string;
}

export interface BroadcastResponse {
  sent_count: number;
  skipped_count: number;
}

// Approvals
export interface PendingAction {
  id: string;
  candidate_id: string;
  action_type: string;
  entity_type: string;
  entity_id: string;
  status: string;
  ai_reasoning: string | null;
  metadata_: Record<string, unknown> | null;
  message_subject: string | null;
  message_body: string | null;
  contact_name: string | null;
  company_name: string | null;
  message_type: string | null;
  channel: string | null;
  reviewed_at: string | null;
  expires_at: string | null;
  created_at: string;
}

export interface PendingActionListResponse {
  actions: PendingAction[];
  total: number;
}

export interface PendingCountResponse {
  count: number;
}
