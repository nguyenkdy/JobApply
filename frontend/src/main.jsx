import React, { createContext, useContext, useEffect, useState } from 'react';
import { createRoot } from 'react-dom/client';
import { BrowserRouter, Link, NavLink, Navigate, Route, Routes, useNavigate, useParams, useSearchParams } from 'react-router-dom';
import { ArrowUpRight, ArrowRight, BriefcaseBusiness, MapPin, Search, SlidersHorizontal, Building2, FileText, Plus, Check, ChevronRight, Clock3, LogOut, Menu, X, Download, Send, Sparkles } from 'lucide-react';
import { api, downloadCV } from './api';
import './styles.css';
const Auth = createContext(null);
const labels = {
  Draft: 'Bản nháp',
  Published: 'Đang tuyển',
  Closed: 'Đã đóng',
  Submitted: 'Đã nộp',
  Reviewing: 'Đang xét',
  Interview: 'Phỏng vấn',
  Offered: 'Đề nghị nhận việc',
  Rejected: 'Từ chối',
  Withdrawn: 'Đã rút',
  Onsite: 'Tại văn phòng',
  Hybrid: 'Kết hợp',
  Remote: 'Từ xa'
};
const nextStatuses = {
  Submitted: ['Reviewing', 'Rejected'],
  Reviewing: ['Interview', 'Rejected'],
  Interview: ['Offered', 'Rejected']
};
const date = value => new Date(value).toLocaleDateString('vi-VN');
const dateTime = value => new Date(value).toLocaleString('vi-VN');
const levels = ['Intern', 'Junior', 'Middle', 'Senior', 'Lead'];
const modes = ['Onsite', 'Hybrid', 'Remote'];
function Badge({
  status
}) {
  return <span className={`badge ${status}`}>{labels[status] || status}</span>;
}
function Empty({
  title = 'Chưa có dữ liệu',
  children
}) {
  return <div className="empty"><FileText size={32} /><h3>{title}</h3><p>{children}</p></div>;
}
function Notice({
  error,
  success
}) {
  return <>{error && <div className="notice error" role="alert">{error}</div>}{success && <div className="notice success" role="status"><Check size={17} />{success}</div>}</>;
}
function Loading() {
  return <div className="loading" role="status"><span className="spinner" />Đang tải dữ liệu…</div>;
}
function Field({
  label,
  children,
  ...props
}) {
  return <label className="field"><span>{label}</span>{children || <input {...props} />}</label>;
}
function useAuth() {
  return useContext(Auth);
}
function useLoad(loader, dependencies) {
  const [data, setData] = useState(null),
    [error, setError] = useState(''),
    [loading, setLoading] = useState(true),
    [version, setVersion] = useState(0);
  useEffect(() => {
    let active = true;
    setLoading(true);
    setError('');
    Promise.resolve().then(loader).then(value => {
      if (active) setData(value);
    }).catch(e => {
      if (active) setError(e.message);
    }).finally(() => {
      if (active) setLoading(false);
    });
    return () => {
      active = false;
    };
  }, [...dependencies, version]);
  return {
    data,
    error,
    loading,
    reload: () => setVersion(v => v + 1)
  };
}
function DataView({
  state,
  children
}) {
  if (state.loading) return <Loading />;
  if (state.error) return <div className="panel"><Notice error={state.error} /><button className="button secondary" onClick={state.reload}>Thử lại</button></div>;
  return children(state.data);
}
function Title({
  eyebrow,
  title,
  children,
  action
}) {
  return <div className="page-title"><div><div className="eyebrow">{eyebrow}</div><h1>{title}</h1>{children && <p>{children}</p>}</div>{action}</div>;
}
function App() {
  const [session, setSession] = useState(() => {
    try {
      return JSON.parse(sessionStorage.getItem('jobapply-session'));
    } catch {
      return null;
    }
  });
  const [expired, setExpired] = useState(false),
    [menu, setMenu] = useState(false);
  const login = value => {
    sessionStorage.setItem('jobapply-session', JSON.stringify(value));
    setSession(value);
    setExpired(false);
  };
  const logout = () => {
    sessionStorage.removeItem('jobapply-session');
    setSession(null);
    setMenu(false);
  };
  useEffect(() => {
    const handler = () => {
      logout();
      setExpired(true);
    };
    window.addEventListener('session-expired', handler);
    return () => window.removeEventListener('session-expired', handler);
  }, []);
  const auth = {
    user: session?.user,
    token: session?.access_token,
    login,
    logout
  };
  const recruiter = auth.user?.role === 'Recruiter';
  return <Auth.Provider value={auth}><header className="header"><div className="header-inner"><Link className="brand" to="/"><span className="brand-icon"><BriefcaseBusiness size={20} /></span>Job<span>Apply</span><span className="brand-dot">.</span></Link><button className="icon-button mobile-menu" aria-label="Mở menu" onClick={() => setMenu(!menu)}>{menu ? <X /> : <Menu />}</button><nav className={menu ? 'nav open' : 'nav'} onClick={() => setMenu(false)}><NavLink to="/" end>Tìm việc làm</NavLink>{auth.user && (recruiter ? <><NavLink to="/recruiter">Tổng quan</NavLink><NavLink to="/company">Công ty</NavLink></> : <><NavLink to="/applications">Hồ sơ ứng tuyển</NavLink><NavLink to="/profile">Hồ sơ & CV</NavLink></>)}</nav><div className="header-actions">{auth.user ? <><span className="user-name"><span className="avatar">{auth.user.full_name[0]}</span>{auth.user.full_name}</span><button className="icon-button" title="Đăng xuất" aria-label="Đăng xuất" onClick={logout}><LogOut size={18} /></button></> : <><Link className="login-link" to="/login">Đăng nhập</Link><Link className="button small" to="/register">Bắt đầu ngay <ArrowUpRight size={16} /></Link></>}</div></div></header>
    {expired && <div className="container"><Notice error="Phiên đăng nhập đã hết hạn. Vui lòng đăng nhập lại." /></div>}
    <main><Routes><Route path="/" element={<JobSearch />} /><Route path="/jobs/:id" element={<JobDetail />} /><Route path="/login" element={<AuthPage />} /><Route path="/register" element={<AuthPage register />} /><Route path="/profile" element={<Guard role="Candidate"><Profile /></Guard>} /><Route path="/applications" element={<Guard role="Candidate"><Applications /></Guard>} /><Route path="/applications/:id" element={<Guard><ApplicationDetail /></Guard>} /><Route path="/company" element={<Guard role="Recruiter"><Company /></Guard>} /><Route path="/recruiter" element={<Guard role="Recruiter"><Dashboard /></Guard>} /><Route path="/recruiter/jobs/new" element={<Guard role="Recruiter"><JobEditor /></Guard>} /><Route path="/recruiter/jobs/:id/edit" element={<Guard role="Recruiter"><JobEditor /></Guard>} /><Route path="/recruiter/jobs/:id/applications" element={<Guard role="Recruiter"><Applicants /></Guard>} /><Route path="*" element={<div className="container"><Empty title="Không tìm thấy trang"><Link to="/">Về trang tìm việc</Link></Empty></div>} /></Routes></main>
    <footer><div className="container footer-inner"><Link className="brand" to="/">Job<span>Apply</span>.</Link><span>Một cơ hội mới. Một hành trình mới.</span><span className="footer-note">Đồ án cá nhân · Chạy trên máy local</span></div></footer></Auth.Provider>;
}
function Guard({
  role,
  children
}) {
  const {
    user
  } = useAuth();
  if (!user) return <Navigate to="/login" replace />;
  if (role && user.role !== role) return <Navigate to="/" replace />;
  return children;
}
function JobSearch() {
  const [params, setParams] = useSearchParams();
  const [query, setQuery] = useState(params.get('q') || '');
  const state = useLoad(() => api(`/job/jobs?${params.toString()}&limit=12`), [params.toString()]);
  const update = (key, value) => {
    const next = new URLSearchParams(params);
    value ? next.set(key, value) : next.delete(key);
    next.delete('offset');
    setParams(next);
  };
  const offset = Number(params.get('offset') || 0);
  const turnPage = value => {
    const next = new URLSearchParams(params);
    next.set('offset', value);
    setParams(next);
  };
  return <><section className="hero"><div className="container hero-layout"><div className="hero-copy"><div className="eyebrow"><span className="live-dot" /> SẴN SÀNG CHO BƯỚC TIẾP THEO</div><h1>Công việc phù hợp.<br /><span>Tương lai rộng mở.</span></h1><p>Kết nối với cơ hội dành cho bạn. Tìm việc, gửi hồ sơ<br className="desktop-only" /> và theo dõi hành trình ứng tuyển tại một nơi.</p><form className="search-bar" onSubmit={e => {
            e.preventDefault();
            update('q', query);
          }}><Search size={22} /><input aria-label="Từ khóa công việc" placeholder="Vị trí, kỹ năng hoặc tên công ty…" value={query} onChange={e => setQuery(e.target.value)} /><button className="button" type="submit">Tìm việc <ArrowRight size={17} /></button></form><div className="popular"><span>Thử tìm:</span>{['Python', 'React', 'Designer'].map(item => <button key={item} onClick={() => {
              setQuery(item);
              update('q', item);
            }}>{item}<ArrowUpRight size={13} /></button>)}</div></div><div className="hero-art" aria-hidden="true"><div className="orbit orbit-one" /><div className="orbit orbit-two" /><div className="art-star">✳</div><div className="floating-label"><span className="mini-check"><Check size={15} /></span>Thêm một bước tiến</div><div className="opportunity-card"><div className="art-icon"><BriefcaseBusiness size={30} /></div><div className="art-line long" /><div className="art-line" /><div className="art-tags"><i /><i /></div><div className="art-bottom"><span>CƠ HỘI CỦA BẠN</span><ArrowUpRight size={28} /></div></div><div className="floating-bottom"><Sparkles size={18} /> Bắt đầu hành trình mới</div></div></div></section>
    <div className="container discovery"><aside className="filters"><div className="filter-heading"><h3><SlidersHorizontal size={18} />Bộ lọc</h3><button className="text-button" onClick={() => {
            setParams({});
            setQuery('');
          }}>Đặt lại</button></div><Field label="Địa điểm"><select value={params.get('location') || ''} onChange={e => update('location', e.target.value)}><option value="">Tất cả địa điểm</option>{['Hồ Chí Minh', 'Hà Nội', 'Đà Nẵng'].map(item => <option key={item}>{item}</option>)}</select></Field><div className="filter-group"><h4>Cấp bậc</h4>{['', ...levels].map(item => <label className="radio-row" key={item}><input type="radio" name="level" checked={(params.get('level') || '') === item} onChange={() => update('level', item)} />{item || 'Tất cả cấp bậc'}</label>)}</div><div className="filter-group"><h4>Hình thức làm việc</h4>{['', ...modes].map(item => <label className="radio-row" key={item}><input type="radio" name="mode" checked={(params.get('work_mode') || '') === item} onChange={() => update('work_mode', item)} />{labels[item] || 'Tất cả hình thức'}</label>)}</div><div className="filter-tip"><FileText size={24} /><h4>Cơ hội bắt đầu từ hồ sơ tốt.</h4><p>Cập nhật kỹ năng và CV để sẵn sàng cho vị trí tiếp theo.</p><Link to="/profile">Hoàn thiện hồ sơ <ArrowRight size={15} /></Link></div></aside><section className="results"><div className="section-heading"><div className="heading-with-line"><span className="tiny-label">KHÁM PHÁ CƠ HỘI</span><h2>Việc làm dành cho bạn<span className="green-dot">.</span></h2></div><span className="sort-label">Mới nhất trước</span></div><DataView state={state}>{jobs => <><p className="result-count">{jobs.length ? `Hiển thị ${offset + 1}–${offset + jobs.length} cơ hội đang tuyển` : 'Không có kết quả phù hợp'}{params.get('q') && <> cho <strong>“{params.get('q')}”</strong></>}</p><div className="job-grid">{jobs.map(job => <JobCard key={job.id} job={job} />)}</div>{!jobs.length && <Empty title="Chưa tìm thấy cơ hội phù hợp">Thử từ khóa khác hoặc mở rộng bộ lọc của bạn.</Empty>}<div className="pagination"><button disabled={!offset} className="button secondary" onClick={() => turnPage(Math.max(0, offset - 12))}>Trang trước</button>{jobs.length === 12 && <button className="button secondary" onClick={() => turnPage(offset + 12)}>Trang tiếp <ArrowRight size={16} /></button>}</div></>}</DataView></section></div></>;
}
function JobCard({
  job
}) {
  return <Link className="job-card" to={`/jobs/${job.id}`}><div className="job-card-top"><span className={`company-logo tone-${job.company.name.length % 4}`}>{job.company.name.split(' ').map(word => word[0]).slice(0, 2).join('')}</span><span className="job-mode">{labels[job.work_mode]}</span></div><p className="company-name">{job.company.name}</p><h3>{job.title}</h3><div className="job-meta"><span><MapPin size={14} />{job.location}</span><span>·</span><span>{job.level}</span></div><div className="job-card-bottom"><div><strong>{job.salary || 'Lương thỏa thuận'}</strong><small>Hạn nộp {date(job.deadline)}</small></div><span className="card-arrow"><ArrowUpRight size={20} /></span></div></Link>;
}
function AuthPage({
  register = false
}) {
  const {
      login,
      user
    } = useAuth(),
    navigate = useNavigate();
  const [error, setError] = useState(''),
    [busy, setBusy] = useState(false);
  if (user) return <Navigate to={user.role === 'Recruiter' ? '/recruiter' : '/'} replace />;
  const submit = async e => {
    e.preventDefault();
    setBusy(true);
    setError('');
    const fields = Object.fromEntries(new FormData(e.currentTarget));
    try {
      if (register) await api('/account/auth/register', {
        method: 'POST',
        body: fields
      });
      const data = await api('/account/auth/login', {
        method: 'POST',
        body: {
          email: fields.email,
          password: fields.password
        }
      });
      login(data);
      navigate(data.user.role === 'Recruiter' ? '/recruiter' : '/');
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  };
  return <div className="container auth-layout"><div className="auth-intro"><div className="eyebrow">HÀNH TRÌNH CỦA BẠN, BẮT ĐẦU TẠI ĐÂY</div><h1>Mở cánh cửa<br />đến cơ hội mới.</h1><p>Một hồ sơ. Nhiều cơ hội.<br />Chủ động với từng bước đi trong sự nghiệp.</p><div className="auth-decoration"><BriefcaseBusiness size={78} /><Sparkles size={36} /></div></div><form key={register ? 'register' : 'login'} className="panel auth-form" onSubmit={submit}><h2>{register ? 'Tạo tài khoản' : 'Chào mừng trở lại'}</h2><p className="muted">{register ? 'Cùng JobApply viết tiếp hành trình của bạn.' : 'Đăng nhập để tiếp tục hành trình của bạn.'}</p><Notice error={error} />{register && <><Field label="Họ và tên" name="full_name" minLength={2} maxLength={120} required autoComplete="name" /><Field label="Bạn là"><select name="role"><option value="Candidate">Ứng viên tìm việc</option><option value="Recruiter">Nhà tuyển dụng</option></select></Field></>}<Field label="Email" name="email" type="email" required autoComplete="email" /><Field label="Mật khẩu" name="password" type="password" minLength={register ? 8 : 1} maxLength={128} required autoComplete={register ? 'new-password' : 'current-password'} />{register && <small className="muted">Tối thiểu 8 ký tự.</small>}<button className="button full" disabled={busy}>{busy ? 'Đang xử lý…' : register ? 'Tạo tài khoản' : 'Đăng nhập'}<ArrowRight size={18} /></button><p className="auth-switch">{register ? 'Đã có tài khoản?' : 'Chưa có tài khoản?'} <Link to={register ? '/login' : '/register'} onClick={() => setError('')}>{register ? 'Đăng nhập' : 'Đăng ký ngay'}</Link></p></form></div>;
}
function JobDetail() {
  const {
      id
    } = useParams(),
    {
      user,
      token
    } = useAuth();
  const state = useLoad(() => api(`/job/jobs/${id}`), [id]);
  const cvs = useLoad(() => user?.role === 'Candidate' ? api('/account/cvs', {
    token
  }) : [], [token]);
  const [error, setError] = useState(''),
    [success, setSuccess] = useState(''),
    [busy, setBusy] = useState(false),
    [applicationId, setApplicationId] = useState('');
  const submit = async e => {
    e.preventDefault();
    setBusy(true);
    setError('');
    try {
      const body = {
        ...Object.fromEntries(new FormData(e.currentTarget)),
        job_id: id
      };
      const data = await api('/application/applications', {
        token,
        method: 'POST',
        body
      });
      setApplicationId(data.id);
      setSuccess('Đã gửi hồ sơ ứng tuyển thành công.');
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  };
  return <div className="container page"><Link className="back-link" to="/">← Tất cả việc làm</Link><DataView state={state}>{job => <><Title eyebrow={job.company.name} title={job.title} action={<Badge status={job.status} />}>{job.location} · {job.level} · {labels[job.work_mode]}</Title><div className="detail-layout"><div className="panel"><div className="facts"><div><span>Mức lương</span><strong>{job.salary || 'Thỏa thuận'}</strong></div><div><span>Hạn ứng tuyển</span><strong>{date(job.deadline)}</strong></div></div><h2>Mô tả công việc</h2><p className="prose">{job.description}</p><h2>Yêu cầu ứng viên</h2><p className="prose">{job.requirements}</p><hr /><h2>Về {job.company.name}</h2><p className="prose">{job.company.description}</p><p className="muted"><MapPin size={15} />{job.company.location}</p>{job.company.website && <a className="text-link" href={job.company.website} target="_blank" rel="noreferrer">Website công ty <ArrowUpRight size={15} /></a>}</div><aside className="panel apply-panel"><span className="circle-icon"><Send size={23} /></span><h2>Đón lấy cơ hội này</h2><p className="muted">Gửi phiên bản CV phù hợp nhất và đôi lời giới thiệu về bạn.</p><Notice error={error} success={success} />{applicationId ? <Link className="button full" to={`/applications/${applicationId}`}>Xem hồ sơ đã nộp</Link> : job.status !== 'Published' || new Date(job.deadline) <= new Date() ? <Empty title="Đã ngừng nhận hồ sơ">Hãy khám phá những cơ hội khác.</Empty> : !user ? <Link className="button full" to="/login">Đăng nhập để ứng tuyển</Link> : user.role !== 'Candidate' ? <p>Tài khoản nhà tuyển dụng không thể ứng tuyển.</p> : <DataView state={cvs}>{items => items.length ? <form onSubmit={submit}><Field label="Chọn phiên bản CV"><select name="cv_id" required>{items.map(cv => <option key={cv.id} value={cv.id}>{cv.name}</option>)}</select></Field><Field label="Lời giới thiệu"><textarea name="introduction" rows={5} maxLength={5000} placeholder="Điều gì khiến bạn phù hợp với vị trí này?" /></Field><button disabled={busy} className="button full">{busy ? 'Đang gửi…' : 'Gửi hồ sơ ứng tuyển'}<ArrowRight size={16} /></button><small className="muted">Mỗi vị trí chỉ được ứng tuyển một lần.</small></form> : <><p>Bạn chưa có CV. Tải lên CV PDF để bắt đầu.</p><Link className="button full" to="/profile">Thêm CV</Link></>}</DataView>}</aside></div></>}</DataView></div>;
}
function Profile() {
  const {
    token
  } = useAuth();
  const state = useLoad(async () => ({
    profile: await api('/account/me', {
      token
    }),
    cvs: await api('/account/cvs', {
      token
    })
  }), [token]);
  const [error, setError] = useState(''),
    [success, setSuccess] = useState(''),
    [busy, setBusy] = useState(false);
  const save = async e => {
    e.preventDefault();
    const form = e.currentTarget;
    setBusy(true);
    setError('');
    setSuccess('');
    try {
      const body = Object.fromEntries(new FormData(form));
      body.skills = body.skills.split(',').map(s => s.trim()).filter(Boolean);
      await api('/account/me', {
        token,
        method: 'PUT',
        body
      });
      setSuccess('Đã lưu hồ sơ cá nhân.');
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  };
  const upload = async e => {
    e.preventDefault();
    const form = e.currentTarget;
    setBusy(true);
    setError('');
    setSuccess('');
    try {
      await api('/account/cvs', {
        token,
        method: 'POST',
        body: new FormData(form)
      });
      form.reset();
      state.reload();
      setSuccess('Đã thêm phiên bản CV mới.');
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  };
  const download = async cv => {
    try {
      await downloadCV(cv.download_url, token);
    } catch (e) {
      setError(e.message);
    }
  };
  return <div className="container page"><Title eyebrow="KHÔNG GIAN CỦA BẠN" title="Hồ sơ & CV">Giới thiệu bản thân, để cơ hội tìm thấy bạn.</Title><Notice error={error} success={success} /><DataView state={state}>{({
        profile,
        cvs
      }) => <div className="two-columns"><form className="panel" onSubmit={save}><h2>Thông tin cá nhân</h2><Field label="Họ và tên" name="full_name" defaultValue={profile.full_name} required minLength={2} maxLength={120} /><Field label="Giới thiệu ngắn"><textarea name="bio" rows={4} defaultValue={profile.bio} maxLength={3000} /></Field><Field label="Kỹ năng (cách nhau bằng dấu phẩy)" name="skills" defaultValue={profile.skills.join(', ')} placeholder="Python, React, SQL" /><Field label="Địa điểm" name="location" maxLength={120} defaultValue={profile.location} /><Field label="Thông tin liên hệ" name="contact" maxLength={255} defaultValue={profile.contact} placeholder="Số điện thoại hoặc địa chỉ liên hệ" /><button className="button" disabled={busy}>Lưu hồ sơ <Check size={16} /></button></form><section className="panel"><h2>Thư viện CV</h2><p className="muted">Mỗi CV là một phiên bản riêng. Hồ sơ đã nộp luôn giữ nguyên phiên bản CV tại thời điểm ứng tuyển.</p><div className="cv-list">{cvs.map(cv => <div className="cv-row" key={cv.id}><FileText /><div><strong>{cv.name}</strong><small>{date(cv.created_at)} · {Math.ceil(cv.size / 1024)} KB</small></div><button className="icon-button" onClick={() => download(cv)} aria-label={`Tải ${cv.name}`}><Download size={18} /></button></div>)}{!cvs.length && <Empty title="Chưa có CV">Thêm CV đầu tiên để sẵn sàng ứng tuyển.</Empty>}</div><form className="upload-box" onSubmit={upload}><h3><Plus size={18} />Thêm phiên bản CV</h3><Field label="Tên phiên bản" name="name" required maxLength={120} placeholder="VD: CV Frontend — tháng 9" /><Field label="File PDF · tối đa 5 MB" name="file" type="file" accept="application/pdf,.pdf" required /><button className="button secondary full" disabled={busy}>{busy ? 'Đang xử lý…' : 'Tải CV lên'}</button></form></section></div>}</DataView></div>;
}
function ApplicationList({
  items,
  recruiter = false
}) {
  return items.length ? <div className="application-list">{items.map(item => <Link className="application-row" key={item.id} to={`/applications/${item.id}`}><span className="document-icon"><FileText size={22} /></span><div className="application-main"><h3>{recruiter ? item.candidate.full_name : item.job.title}</h3><p>{recruiter ? item.candidate.email : item.job.company.name} · {date(item.created_at)}</p></div><Badge status={item.status} /><ChevronRight size={20} /></Link>)}</div> : <Empty title="Chưa có hồ sơ">Hồ sơ ứng tuyển sẽ xuất hiện tại đây.</Empty>;
}
function Applications() {
  const {
    token
  } = useAuth();
  const state = useLoad(() => api('/application/applications', {
    token
  }), [token]);
  return <div className="container page"><Title eyebrow="HÀNH TRÌNH ỨNG TUYỂN" title="Hồ sơ đã nộp" action={<Link className="button secondary" to="/">Tìm thêm cơ hội <ArrowUpRight size={16} /></Link>}>Theo dõi từng bước tiến đến công việc tiếp theo.</Title><DataView state={state}>{items => <ApplicationList items={items} />}</DataView></div>;
}
function ApplicationDetail() {
  const {
      id
    } = useParams(),
    {
      token,
      user
    } = useAuth();
  const state = useLoad(() => api(`/application/applications/${id}`, {
    token
  }), [id, token]);
  const [error, setError] = useState(''),
    [success, setSuccess] = useState(''),
    [busy, setBusy] = useState(false);
  const change = async status => {
    if (status === 'Withdrawn' && !window.confirm('Rút hồ sơ này? Bạn sẽ không thể ứng tuyển lại job này.')) return;
    setBusy(true);
    setError('');
    try {
      await api(`/application/applications/${id}/status`, {
        token,
        method: 'PATCH',
        body: {
          status
        }
      });
      setSuccess('Đã cập nhật trạng thái hồ sơ.');
      state.reload();
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  };
  return <div className="container page"><Notice error={error} success={success} /><DataView state={state}>{item => <><Title eyebrow="CHI TIẾT HỒ SƠ" title={item.job.title} action={<Badge status={item.status} />}>{item.job.company.name} · Nộp ngày {dateTime(item.created_at)}</Title><div className="detail-layout"><section className="panel"><h2>{item.candidate.full_name}</h2><p className="muted">{item.candidate.email} · {item.candidate.location}</p><p>{item.candidate.contact}</p><p className="prose">{item.candidate.bio}</p><div className="tags">{item.candidate.skills.map((skill, i) => <span key={i}>{skill}</span>)}</div><h3>Lời giới thiệu</h3><p className="prose">{item.introduction || 'Ứng viên không gửi lời giới thiệu.'}</p><hr /><h3>CV đã nộp · {item.cv.name}</h3><p className="muted">Phiên bản lưu tại thời điểm ứng tuyển.</p><button className="button secondary" onClick={async () => {
              try {
                await downloadCV(item.download_url, token);
              } catch (e) {
                setError(e.message);
              }
            }}><Download size={17} />Tải CV PDF</button><hr /><h3>Thông tin vị trí lúc ứng tuyển</h3><p>{item.job.location} · {labels[item.job.work_mode]} · {item.job.salary || 'Lương thỏa thuận'}</p><p className="prose">{item.job.description}</p><h4>Yêu cầu</h4><p className="prose">{item.job.requirements}</p></section><aside><section className="panel"><h2>Cập nhật trạng thái</h2>{user.role === 'Recruiter' ? <div className="stack">{(nextStatuses[item.status] || []).map(status => <button disabled={busy} key={status} className={`button ${status === 'Rejected' ? 'danger' : ''}`} onClick={() => change(status)}>{labels[status]}</button>)}{!nextStatuses[item.status] && <p className="muted">Hồ sơ đã kết thúc.</p>}</div> : nextStatuses[item.status] ? <button className="button danger full" disabled={busy} onClick={() => change('Withdrawn')}>Rút hồ sơ</button> : <p className="muted">Hồ sơ đã kết thúc.</p>}</section><section className="panel history"><h2><Clock3 size={20} />Lịch sử hồ sơ</h2>{item.history.map((event, i) => <div className="history-item" key={i}><span className="history-dot" /><strong>{event.old_status ? `${labels[event.old_status]} → ` : ''}{labels[event.new_status]}</strong><small>{dateTime(event.created_at)}</small><small>{event.actor_role === 'Candidate' ? 'Ứng viên' : 'Nhà tuyển dụng'} · {event.actor_id.slice(0, 8)}</small></div>)}</section></aside></div></>}</DataView></div>;
}
function Company() {
  const {
      token
    } = useAuth(),
    state = useLoad(() => api('/job/companies/mine', {
      token
    }), [token]);
  const [error, setError] = useState(''),
    [success, setSuccess] = useState(''),
    [busy, setBusy] = useState(false);
  const submit = async e => {
    e.preventDefault();
    setBusy(true);
    setError('');
    try {
      await api(state.data ? `/job/companies/${state.data.id}` : '/job/companies', {
        token,
        method: state.data ? 'PUT' : 'POST',
        body: Object.fromEntries(new FormData(e.currentTarget))
      });
      setSuccess('Đã lưu hồ sơ công ty.');
      state.reload();
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  };
  return <div className="container page narrow"><Title eyebrow="DÀNH CHO NHÀ TUYỂN DỤNG" title="Hồ sơ công ty">Xây dựng hình ảnh công ty trong mắt ứng viên.</Title><Notice error={error} success={success} /><DataView state={state}>{company => <form className="panel" onSubmit={submit}><Field label="Tên công ty" name="name" defaultValue={company?.name} minLength={2} maxLength={160} required /><Field label="Giới thiệu công ty"><textarea name="description" rows={7} defaultValue={company?.description} maxLength={10000} /></Field><Field label="Địa điểm" name="location" maxLength={120} defaultValue={company?.location} /><Field label="Website" name="website" type="url" maxLength={255} defaultValue={company?.website} placeholder="https://…" /><button className="button" disabled={busy}>{busy ? 'Đang lưu…' : company ? 'Lưu thay đổi' : 'Tạo công ty'}<Check size={16} /></button></form>}</DataView></div>;
}
function Dashboard() {
  const {
    token,
    user
  } = useAuth();
  const state = useLoad(async () => {
    const [company, jobs] = await Promise.all([api('/job/companies/mine', {
      token
    }), api('/job/jobs/mine', {
      token
    })]);
    const rows = await Promise.all(jobs.map(job => api(`/application/applications?job_id=${job.id}`, {
      token
    })));
    return {
      company,
      jobs,
      applications: rows.flat(),
      counts: Object.fromEntries(jobs.map((job, i) => [job.id, rows[i].length]))
    };
  }, [token]);
  const [error, setError] = useState(''),
    [busy, setBusy] = useState(false);
  const change = async (id, status) => {
    setBusy(true);
    setError('');
    try {
      await api(`/job/jobs/${id}/status`, {
        token,
        method: 'PATCH',
        body: {
          status
        }
      });
      state.reload();
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  };
  return <div className="container page"><Title eyebrow="KHÔNG GIAN NHÀ TUYỂN DỤNG" title={`Xin chào, ${user.full_name}`} action={<Link className="button" to="/recruiter/jobs/new"><Plus size={18} />Tạo tin tuyển dụng</Link>}>Tổng quan hoạt động tuyển dụng của công ty bạn.</Title><Notice error={error} /><DataView state={state}>{({
        company,
        jobs,
        applications,
        counts
      }) => <>{!company && <div className="setup-banner"><Building2 /><div><h3>Bắt đầu với hồ sơ công ty</h3><p>Tạo công ty trước khi đăng tin tuyển dụng đầu tiên.</p></div><Link className="button" to="/company">Tạo công ty <ArrowRight size={16} /></Link></div>}<div className="stats"><div className="stat"><BriefcaseBusiness /><span>Tổng tin tuyển dụng</span><strong>{jobs.length}</strong></div><div className="stat"><span className="live-dot" /><span>Đang tuyển</span><strong>{jobs.filter(job => job.status === 'Published' && new Date(job.deadline) > new Date()).length}</strong></div><div className="stat"><FileText /><span>Hồ sơ nhận được</span><strong>{applications.length}</strong></div><div className="stat"><Clock3 /><span>Chờ xét duyệt</span><strong>{applications.filter(item => item.status === 'Submitted').length}</strong></div></div><div className="section-heading"><h2>Tin tuyển dụng của bạn</h2><span className="muted">{company?.name}</span></div>{!jobs.length ? <Empty title="Chưa có tin tuyển dụng">Tạo bản nháp và đăng tin để kết nối với ứng viên.</Empty> : <div className="recruiter-jobs">{jobs.map(job => <div className="recruiter-job" key={job.id}><div><h3>{job.title}</h3><p>{job.location} · {job.level} · Hạn {date(job.deadline)}</p><Badge status={job.status} /></div><div className="job-actions"><Link className="button secondary small" to={`/recruiter/jobs/${job.id}/applications`}>{counts[job.id]} hồ sơ <ChevronRight size={15} /></Link>{job.status === 'Draft' && <><Link className="text-link" to={`/recruiter/jobs/${job.id}/edit`}>Chỉnh sửa</Link><button disabled={busy} className="button small" onClick={() => change(job.id, 'Published')}>Đăng tin</button></>}{job.status === 'Published' && <button disabled={busy} className="button secondary small" onClick={() => change(job.id, 'Closed')}>Đóng tin</button>}</div></div>)}</div>}</>}</DataView></div>;
}
function JobEditor() {
  const {
      id
    } = useParams(),
    {
      token
    } = useAuth(),
    navigate = useNavigate();
  const state = useLoad(() => id ? api(`/job/jobs/${id}/manage`, {
    token
  }) : null, [id, token]);
  const [error, setError] = useState(''),
    [busy, setBusy] = useState(false);
  const submit = async e => {
    e.preventDefault();
    setBusy(true);
    setError('');
    try {
      const body = Object.fromEntries(new FormData(e.currentTarget));
      body.deadline = new Date(body.deadline).toISOString();
      await api(id ? `/job/jobs/${id}` : '/job/jobs', {
        token,
        method: id ? 'PUT' : 'POST',
        body
      });
      navigate('/recruiter');
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  };
  const localDateTime = value => {
    const d = new Date(value);
    return new Date(d.getTime() - d.getTimezoneOffset() * 60000).toISOString().slice(0, 16);
  };
  return <div className="container page narrow"><Link className="back-link" to="/recruiter">← Tổng quan tuyển dụng</Link><Title eyebrow="TÌM ĐỒNG ĐỘI MỚI" title={id ? 'Chỉnh sửa bản nháp' : 'Tạo tin tuyển dụng'}>Lưu bản nháp trước, sau đó đăng tin từ trang tổng quan.</Title><Notice error={error} /><DataView state={state}>{job => job && job.status !== 'Draft' ? <Empty title="Chỉ có thể chỉnh sửa bản nháp" /> : <form className="panel" onSubmit={submit}><Field label="Tên vị trí" name="title" required minLength={3} maxLength={160} defaultValue={job?.title} /><div className="form-grid"><Field label="Địa điểm" name="location" required minLength={2} maxLength={120} defaultValue={job?.location} /><Field label="Mức lương" name="salary" maxLength={120} defaultValue={job?.salary} placeholder="VD: 20–30 triệu / tháng" /><Field label="Cấp bậc"><select name="level" defaultValue={job?.level || 'Junior'}>{levels.map(item => <option key={item}>{item}</option>)}</select></Field><Field label="Hình thức"><select name="work_mode" defaultValue={job?.work_mode || 'Onsite'}>{modes.map(item => <option key={item} value={item}>{labels[item]}</option>)}</select></Field></div><Field label="Hạn ứng tuyển (giờ địa phương)" name="deadline" type="datetime-local" required defaultValue={job ? localDateTime(job.deadline) : ''} /><Field label="Mô tả công việc"><textarea name="description" rows={7} required minLength={10} maxLength={20000} defaultValue={job?.description} /></Field><Field label="Yêu cầu ứng viên"><textarea name="requirements" rows={6} required minLength={10} maxLength={20000} defaultValue={job?.requirements} /></Field><button disabled={busy} className="button">{busy ? 'Đang lưu…' : 'Lưu bản nháp'}<Check size={17} /></button></form>}</DataView></div>;
}
function Applicants() {
  const {
      id
    } = useParams(),
    {
      token
    } = useAuth();
  const [status, setStatus] = useState('');
  const state = useLoad(async () => ({
    job: await api(`/job/jobs/${id}/manage`, {
      token
    }),
    items: await api(`/application/applications?job_id=${id}&status=${status}`, {
      token
    })
  }), [id, token, status]);
  return <div className="container page"><Link className="back-link" to="/recruiter">← Tổng quan tuyển dụng</Link><Title eyebrow="QUẢN LÝ ỨNG VIÊN" title="Hồ sơ ứng tuyển" /><Field label="Lọc trạng thái"><select value={status} onChange={e => setStatus(e.target.value)}><option value="">Tất cả trạng thái</option>{['Submitted', 'Reviewing', 'Interview', 'Offered', 'Rejected', 'Withdrawn'].map(item => <option key={item} value={item}>{labels[item]}</option>)}</select></Field><DataView state={state}>{({
        job,
        items
      }) => <><h2>{job.title} <span className="muted">({items.length})</span></h2><ApplicationList items={items} recruiter /></>}</DataView></div>;
}
createRoot(document.getElementById('root')).render(<React.StrictMode><BrowserRouter><App /></BrowserRouter></React.StrictMode>);
