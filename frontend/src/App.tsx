import { useEffect, useState } from 'react'
import './App.css'
import { ApiError, api, type Company, type JobPosting, type NewCompany, type Preferences, type User } from './api'

function splitCommaList(value: string): string[] {
  return value
    .split(',')
    .map((entry) => entry.trim())
    .filter((entry) => entry.length > 0)
}

const FREQUENCY_OPTIONS = [
  { label: 'Hourly', value: '0 * * * *' },
  { label: 'Every 8 Hours', value: '0 */8 * * *' },
  { label: 'Daily', value: '0 8 * * *' },
  { label: 'Weekly', value: '0 8 * * 0' },
]
const DEFAULT_FREQUENCY = FREQUENCY_OPTIONS.find((o) => o.label === 'Daily')!.value

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
    frequency: DEFAULT_FREQUENCY,
  })
  const [formError, setFormError] = useState<string | null>(null)

  const [preferences, setPreferences] = useState<Preferences>({ locations: [], keywords: [] })
  const [locationsInput, setLocationsInput] = useState('')
  const [keywordsInput, setKeywordsInput] = useState('')
  const [preferencesError, setPreferencesError] = useState<string | null>(null)
  const [preferencesSaving, setPreferencesSaving] = useState(false)

  const [scrapingAll, setScrapingAll] = useState(false)
  const [scrapeAllMessage, setScrapeAllMessage] = useState<string | null>(null)

  const loadCompanies = () => {
    setLoading(true)
    api
      .listCompanies()
      .then(setCompanies)
      .catch((e) => setError(String(e)))
      .finally(() => setLoading(false))
  }

  const loadPreferences = () => {
    api
      .getPreferences()
      .then((prefs) => {
        setPreferences(prefs)
        setLocationsInput(prefs.locations.join(', '))
        setKeywordsInput(prefs.keywords.join(', '))
      })
      .catch((e) => setError(String(e)))
  }

  useEffect(() => {
    api
      .me()
      .then(setUser)
      .catch(() => setUser(null))
      .finally(() => setAuthChecked(true))
  }, [])

  useEffect(() => {
    if (user) {
      loadCompanies()
      loadPreferences()
    }
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

  // Re-fetch every already-loaded company's jobs, e.g. so is_recommended reflects
  // newly saved preferences or freshly scraped postings, not just what's expanded.
  const refreshCachedJobs = async () => {
    const cachedCompanyIds = Object.keys(jobsByCompany)
    if (cachedCompanyIds.length === 0) return
    const refreshed = await Promise.all(cachedCompanyIds.map((id) => api.listCompanyJobs(id)))
    setJobsByCompany((prev) => {
      const next = { ...prev }
      cachedCompanyIds.forEach((id, i) => {
        next[id] = refreshed[i]
      })
      return next
    })
  }

  const savePreferences = async (e: React.FormEvent) => {
    e.preventDefault()
    setPreferencesError(null)
    setPreferencesSaving(true)
    try {
      const updated = await api.updatePreferences({
        locations: splitCommaList(locationsInput),
        keywords: splitCommaList(keywordsInput),
      })
      setPreferences(updated)
      await refreshCachedJobs()
    } catch (e) {
      setPreferencesError(String(e))
    } finally {
      setPreferencesSaving(false)
    }
  }

  const scrapeAll = async () => {
    setScrapingAll(true)
    setScrapeAllMessage(null)
    try {
      const result = await api.scrapeAll()
      setScrapeAllMessage(
        `Scraped ${result.companies_scraped} compan${result.companies_scraped === 1 ? 'y' : 'ies'}` +
          (result.companies_failed > 0 ? ` (${result.companies_failed} failed)` : '') +
          ` — ${result.jobs_found} job(s) found. Sent a recommended-jobs email if there were any matches.`,
      )
      await refreshCachedJobs()
    } catch (e) {
      setScrapeAllMessage(`Scrape all failed — ${String(e)}`)
    } finally {
      setScrapingAll(false)
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

  const hasPreferences = preferences.locations.length > 0 || preferences.keywords.length > 0

  // Most-frequent-first (FREQUENCY_OPTIONS is already in that order), then
  // alphabetically by name within the same frequency.
  const sortedCompanies = [...companies].sort((a, b) => {
    const freqDiff =
      FREQUENCY_OPTIONS.findIndex((o) => o.value === a.frequency) -
      FREQUENCY_OPTIONS.findIndex((o) => o.value === b.frequency)
    return freqDiff !== 0 ? freqDiff : a.name.localeCompare(b.name)
  })

  const renderJobItem = (job: JobPosting) => (
    <li key={job.id}>
      {job.url ? (
        <a href={job.url} target="_blank" rel="noreferrer">
          <strong>{job.title}</strong>
        </a>
      ) : (
        <strong>{job.title}</strong>
      )}
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
  )

  if (!authChecked) {
    return <div className="page" />
  }

  if (!user) {
    return (
      <div className="page">
        <h1>Henry</h1>
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
        <h1>Henry</h1>
        <div className="actions">
          <span className="muted">{user.username}</span>
          <button onClick={handleLogout}>Sign Out</button>
        </div>
      </div>

      {loading && <p>Loading companies…</p>}
      {error && <p className="error">{error}</p>}
      {scrapeMessage && <p className="scrape-message">{scrapeMessage}</p>}

      <ul className="companies">
        {sortedCompanies.map((company) => (
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
                  {expandedId === company.id ? 'Hide jobs' : 'View Jobs'}
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
                {jobsByCompany[company.id] != null &&
                  jobsByCompany[company.id]!.length > 0 &&
                  (hasPreferences ? (
                    <>
                      <h4>Good Fits</h4>
                      <ul>
                        {jobsByCompany[company.id]!.filter((job) => job.is_recommended).map(renderJobItem)}
                        {jobsByCompany[company.id]!.every((job) => !job.is_recommended) && (
                          <li className="muted">No matches yet.</li>
                        )}
                      </ul>
                      <h4>Other Openings</h4>
                      <ul>{jobsByCompany[company.id]!.filter((job) => !job.is_recommended).map(renderJobItem)}</ul>
                    </>
                  ) : (
                    <ul>{jobsByCompany[company.id]!.map(renderJobItem)}</ul>
                  ))}
              </div>
            )}
          </li>
        ))}
      </ul>

      <h2>Add Company</h2>
      <form onSubmit={addCompany} className="add-company-form">
        <input
          placeholder="Name"
          value={newCompany.name}
          onChange={(e) => setNewCompany({ ...newCompany, name: e.target.value })}
          required
        />
        <input
          placeholder="Career Page URL"
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

      <h2>Preferences</h2>
      <form onSubmit={savePreferences} className="add-company-form">
        <label className="field">
          <span>Preferred Locations (comma-separated)</span>
          <input
            value={locationsInput}
            onChange={(e) => setLocationsInput(e.target.value)}
          />
        </label>
        <label className="field">
          <span>Keywords (comma-separated)</span>
          <input
            value={keywordsInput}
            onChange={(e) => setKeywordsInput(e.target.value)}
          />
        </label>
        <button type="submit" disabled={preferencesSaving}>
          {preferencesSaving ? 'Saving…' : 'Save'}
        </button>
      </form>
      {preferencesError && <p className="error">{preferencesError}</p>}

      {user.is_staff && (
        <div className="scrape-all">
          <h2>Admin</h2>
          <button onClick={scrapeAll} disabled={scrapingAll}>
            {scrapingAll ? 'Scraping All…' : 'Scrape All & Email Recommended Jobs'}
          </button>
          {scrapeAllMessage && <p className="scrape-message">{scrapeAllMessage}</p>}
        </div>
      )}
    </div>
  )
}

export default App
