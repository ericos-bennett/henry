import { useEffect, useState } from 'react'
import './App.css'
import { ApiError, api, type Company, type JobPosting, type NewCompany, type User } from './api'

const FREQUENCY_OPTIONS = [
  { label: 'Hourly', value: '0 * * * *' },
  { label: 'Every 8 Hours', value: '0 */8 * * *' },
  { label: 'Daily', value: '0 8 * * *' },
  { label: 'Weekly', value: '0 8 * * 0' },
]

function App() {
  const [user, setUser] = useState<User | null>(null)
  const [authChecked, setAuthChecked] = useState(false)
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [loginError, setLoginError] = useState<string | null>(null)

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
    frequency: FREQUENCY_OPTIONS[0].value,
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

  useEffect(() => {
    api
      .me()
      .then(setUser)
      .catch(() => setUser(null))
      .finally(() => setAuthChecked(true))
  }, [])

  useEffect(() => {
    if (user) loadCompanies()
  }, [user])

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault()
    setLoginError(null)
    try {
      const loggedInUser = await api.login(username, password)
      setUser(loggedInUser)
      setPassword('')
    } catch (e) {
      setLoginError(e instanceof ApiError && e.status === 401 ? 'Invalid username or password' : String(e))
    }
  }

  const handleLogout = async () => {
    await api.logout()
    setUser(null)
    setCompanies([])
  }

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

  const changeFrequency = async (company: Company, frequency: string) => {
    try {
      const updated = await api.setCompanyFrequency(company.id, frequency)
      setCompanies((prev) => prev.map((c) => (c.id === company.id ? updated : c)))
    } catch (e) {
      setError(String(e))
    }
  }

  const toggleEnabled = async (company: Company) => {
    try {
      const updated = await api.setCompanyEnabled(company.id, !company.enabled)
      setCompanies((prev) => prev.map((c) => (c.id === company.id ? updated : c)))
    } catch (e) {
      setError(String(e))
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
      setNewCompany({ name: '', url: '', frequency: FREQUENCY_OPTIONS[0].value })
    } catch (e) {
      setFormError(String(e))
    }
  }

  if (!authChecked) {
    return <div className="page" />
  }

  if (!user) {
    return (
      <div className="page">
        <h1>Career Scraper</h1>
        <h2>Sign in</h2>
        <form onSubmit={handleLogin} className="add-company-form">
          <input
            placeholder="username"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            required
          />
          <input
            type="password"
            placeholder="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
          />
          <button type="submit">Sign in</button>
        </form>
        {loginError && <p className="error">{loginError}</p>}
      </div>
    )
  }

  return (
    <div className="page">
      <div className="company-row">
        <h1>Career Scraper</h1>
        <div className="actions">
          <span className="muted">{user.username}</span>
          <button onClick={handleLogout}>Sign out</button>
        </div>
      </div>

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
                  ·{' '}
                  <select
                    className="frequency-select"
                    value={company.frequency}
                    onChange={(e) => changeFrequency(company, e.target.value)}
                  >
                    {FREQUENCY_OPTIONS.map((option) => (
                      <option key={option.value} value={option.value}>
                        {option.label}
                      </option>
                    ))}
                  </select>
                </div>
              </div>
              <div className="actions">
                <button onClick={() => scrape(company.id)} disabled={scrapingId === company.id}>
                  {scrapingId === company.id ? 'Scraping…' : 'Scrape'}
                </button>
                <button onClick={() => toggleJobs(company.id)}>
                  {expandedId === company.id ? 'Hide jobs' : 'View jobs'}
                </button>
                <button onClick={() => toggleEnabled(company)}>
                  {company.enabled ? 'Disable' : 'Enable'}
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
                      {job.is_new && <span className="badge-new">New</span>}
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
        <select
          value={newCompany.frequency}
          onChange={(e) => setNewCompany({ ...newCompany, frequency: e.target.value })}
        >
          {FREQUENCY_OPTIONS.map((option) => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ))}
        </select>
        <button type="submit">Add</button>
      </form>
      {formError && <p className="error">{formError}</p>}
    </div>
  )
}

export default App
