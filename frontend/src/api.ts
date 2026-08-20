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
  id: string
  name: string
  url: string
  frequency: string
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, {
    headers: { 'Content-Type': 'application/json' },
    ...init,
  })
  if (!response.ok) {
    const body = await response.text()
    throw new Error(`${response.status} ${response.statusText}: ${body}`)
  }
  return response.json() as Promise<T>
}

export const api = {
  listCompanies: () => request<Company[]>('/api/companies'),

  createCompany: (company: NewCompany) =>
    request<Company>('/api/companies', {
      method: 'POST',
      body: JSON.stringify(company),
    }),

  deleteCompany: (id: string) =>
    request<{ success: boolean }>(`/api/companies/${id}`, { method: 'DELETE' }),

  listCompanyJobs: (id: string) =>
    request<JobPosting[]>(`/api/companies/${id}/jobs?latest_only=true`),

  scrapeCompany: (id: string) =>
    request<ScrapeResult>(`/api/companies/${id}/scrape`, { method: 'POST' }),
}
