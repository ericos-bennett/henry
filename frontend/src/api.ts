export interface Company {
  id: string
  name: string
  url: string
  frequency: string
  enabled: boolean
}

export interface JobPosting {
  id: number
  job_id: string
  source_company: string
  source_url: string
  scraped_at: string
  is_new: boolean
  is_recommended: boolean
  title: string
  url: string | null
  location: string | null
  department: string | null
  employment_type: string | null
  description: string | null
  posted_date: string | null
  salary_min: number | null
  salary_max: number | null
  salary_currency: string | null
  salary_raw: string | null
}

export interface ScrapeResult {
  company_id: string
  jobs_found: number
  scraped_at: string
}

export interface NewCompany {
  name: string
  url: string
  frequency: string
}

export interface User {
  username: string
}

export interface Preferences {
  locations: string[]
  keywords: string[]
}

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message)
  }
}

function getCookie(name: string): string | null {
  const match = document.cookie.match(new RegExp(`(?:^|; )${name}=([^;]*)`))
  return match ? decodeURIComponent(match[1]) : null
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const method = init?.method ?? 'GET'
  const headers: Record<string, string> = { 'Content-Type': 'application/json' }
  if (method !== 'GET' && method !== 'HEAD') {
    const csrfToken = getCookie('csrftoken')
    if (csrfToken) headers['X-CSRFToken'] = csrfToken
  }
  const response = await fetch(path, { headers, ...init })
  if (!response.ok) {
    const body = await response.text()
    throw new ApiError(response.status, `${response.status} ${response.statusText}: ${body}`)
  }
  if (response.status === 204) return undefined as T
  return response.json() as Promise<T>
}

export const api = {
  login: (username: string, password: string) =>
    request<User>('/api/login', {
      method: 'POST',
      body: JSON.stringify({ username, password }),
    }),

  logout: () => request<{ success: boolean }>('/api/logout', { method: 'POST' }),

  me: () => request<User>('/api/me'),

  listCompanies: () => request<Company[]>('/api/companies'),

  createCompany: (company: NewCompany) =>
    request<Company>('/api/companies', {
      method: 'POST',
      body: JSON.stringify(company),
    }),

  setCompanyEnabled: (id: string, enabled: boolean) =>
    request<Company>(`/api/companies/${id}`, {
      method: 'PATCH',
      body: JSON.stringify({ enabled }),
    }),

  setCompanyFrequency: (id: string, frequency: string) =>
    request<Company>(`/api/companies/${id}`, {
      method: 'PATCH',
      body: JSON.stringify({ frequency }),
    }),

  deleteCompany: (id: string) =>
    request<{ success: boolean }>(`/api/companies/${id}`, { method: 'DELETE' }),

  listCompanyJobs: (id: string) =>
    request<JobPosting[]>(`/api/companies/${id}/jobs?latest_only=true`),

  scrapeCompany: (id: string) =>
    request<ScrapeResult>(`/api/companies/${id}/scrape`, { method: 'POST' }),

  getPreferences: () => request<Preferences>('/api/preferences'),

  updatePreferences: (preferences: Preferences) =>
    request<Preferences>('/api/preferences', {
      method: 'PUT',
      body: JSON.stringify(preferences),
    }),
}
