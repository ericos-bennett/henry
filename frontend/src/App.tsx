import { useEffect, useState } from 'react'
import './App.css'
import { api, type Company, type JobPosting, type NewCompany } from './api'

function App() {
  const [companies, setCompanies] = useState<Company[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const [expandedId, setExpandedId] = useState<string | null>(null)
  const [jobsByCompany, setJobsByCompany] = useState<Record<string, JobPosting[]>>({})
  const [jobsLoadingId, setJobsLoadingId] = useState<string | null>(null)

  const [scrapingId, setScrapingId] = useState<string | null>(null)
  const [scrapeMessage, setScrapeMessage] = useState<string | null>(null)

  const [newCompany, setNewCompany] = useState<NewCompany>({
    name: '',
    url: '',
    frequency: '0 */6 * * *',
  })
  const [formError, setFormError] = useState<string | null>(null)

  const loadCompanies = () => {
    setLoading(true)
    api
      .listCompanies()
      .then(setCompanies)
      .catch((e) => setError(String(e)))
      .finally(() => setLoading(false))
  }

  useEffect(loadCompanies, [])

  const toggleJobs = async (id: string) => {
    if (expandedId === id) {
      setExpandedId(null)
      return
    }
    setExpandedId(id)
    if (!jobsByCompany[id]) {
      setJobsLoadingId(id)
      try {
        const jobs = await api.listCompanyJobs(id)
        setJobsByCompany((prev) => ({ ...prev, [id]: jobs }))
      } catch (e) {
        setError(String(e))
      } finally {
        setJobsLoadingId(null)
      }
    }
  }

  const scrape = async (id: string) => {
    const name = companies.find((c) => c.id === id)?.name ?? id
    setScrapingId(id)
    setScrapeMessage(null)
    try {
      const result = await api.scrapeCompany(id)
      setScrapeMessage(`${name}: found ${result.jobs_found} job(s)`)
      // Refresh cached jobs for this company if currently expanded.
      if (expandedId === id) {
        const jobs = await api.listCompanyJobs(id)
        setJobsByCompany((prev) => ({ ...prev, [id]: jobs }))
      }
    } catch (e) {
      setScrapeMessage(`${name}: scrape failed — ${String(e)}`)
    } finally {
      setScrapingId(null)
    }
  }

  const removeCompany = async (id: string) => {
    try {
      await api.deleteCompany(id)
      setCompanies((prev) => prev.filter((c) => c.id !== id))
    } catch (e) {
      setError(String(e))
    }
  }

  const addCompany = async (e: React.FormEvent) => {
    e.preventDefault()
    setFormError(null)
    try {
      const created = await api.createCompany(newCompany)
      setCompanies((prev) => [...prev, created])
      setNewCompany({ name: '', url: '', frequency: '0 */6 * * *' })
    } catch (e) {
      setFormError(String(e))
    }
  }

  return (
    <div className="page">
      <h1>Career Scraper</h1>

      {loading && <p>Loading companies…</p>}
      {error && <p className="error">{error}</p>}
      {scrapeMessage && <p className="scrape-message">{scrapeMessage}</p>}

      <ul className="companies">
        {companies.map((company) => (
          <li key={company.id} className="company">
            <div className="company-row">
              <div>
                <strong>{company.name}</strong>
                <div className="muted small">
                  <a href={company.url} target="_blank" rel="noreferrer">
                    {company.url}
                  </a>{' '}
                  · {company.frequency} · {company.enabled ? 'enabled' : 'disabled'}
                </div>
              </div>
              <div className="actions">
                <button onClick={() => scrape(company.id)} disabled={scrapingId === company.id}>
                  {scrapingId === company.id ? 'Scraping…' : 'Scrape'}
                </button>
                <button onClick={() => toggleJobs(company.id)}>
                  {expandedId === company.id ? 'Hide jobs' : 'View jobs'}
                </button>
                <button onClick={() => removeCompany(company.id)} className="danger">
                  Delete
                </button>
              </div>
            </div>

            {expandedId === company.id && (
              <div className="jobs">
                {jobsLoadingId === company.id && <p>Loading jobs…</p>}
                {jobsByCompany[company.id]?.length === 0 && <p className="muted">No jobs scraped yet.</p>}
                <ul>
                  {jobsByCompany[company.id]?.map((job) => (
                    <li key={job.id}>
                      <strong>{job.title}</strong>
                      {job.location && ` — ${job.location}`}
                      {job.salary_min != null && job.salary_max != null && (
                        <span className="muted">
                          {' '}
                          (${job.salary_min.toLocaleString()}–${job.salary_max.toLocaleString()}
                          {job.salary_currency ? ` ${job.salary_currency}` : ''})
                        </span>
                      )}
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </li>
        ))}
      </ul>

      <h2>Add a company</h2>
      <form onSubmit={addCompany} className="add-company-form">
        <input
          placeholder="name"
          value={newCompany.name}
          onChange={(e) => setNewCompany({ ...newCompany, name: e.target.value })}
          required
        />
        <input
          placeholder="career page URL"
          value={newCompany.url}
          onChange={(e) => setNewCompany({ ...newCompany, url: e.target.value })}
          required
        />
        <input
          placeholder="cron frequency"
          value={newCompany.frequency}
          onChange={(e) => setNewCompany({ ...newCompany, frequency: e.target.value })}
          required
        />
        <button type="submit">Add</button>
      </form>
      {formError && <p className="error">{formError}</p>}
    </div>
  )
}

export default App
