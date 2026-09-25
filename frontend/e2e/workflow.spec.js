import { test, expect } from '@playwright/test';
test('recruiter publishes, candidate applies, recruiter reviews, candidate sees result', async ({
  browser
}) => {
  const recruiterContext = await browser.newContext();
  const candidateContext = await browser.newContext();
  const recruiter = await recruiterContext.newPage();
  const candidate = await candidateContext.newPage();
  const suffix = Date.now();
  const register = async (page, role, name) => {
    await page.goto('/register');
    await page.getByLabel('Họ và tên').fill(name);
    await page.getByLabel('Bạn là').selectOption(role);
    await page.getByLabel('Email', {
      exact: true
    }).fill(`${role.toLowerCase()}${suffix}@example.com`);
    await page.getByLabel('Mật khẩu').fill('BrowserDemo123!');
    await page.getByRole('button', {
      name: 'Tạo tài khoản'
    }).click();
    await expect(page.getByRole('button', {
      name: 'Đăng xuất'
    })).toBeVisible();
  };
  await register(recruiter, 'Recruiter', 'Nhà tuyển dụng E2E');
  await recruiter.goto('/company');
  await recruiter.getByLabel('Tên công ty').fill(`E2E Company ${suffix}`);
  await recruiter.getByLabel('Giới thiệu công ty').fill('Công ty giả lập trong kiểm thử trình duyệt.');
  await recruiter.getByRole('button', {
    name: 'Tạo công ty'
  }).click();
  await expect(recruiter.getByRole('status')).toContainText('Đã lưu hồ sơ công ty');
  await recruiter.goto('/recruiter/jobs/new');
  await recruiter.getByLabel('Tên vị trí').fill(`Python E2E ${suffix}`);
  await recruiter.getByLabel('Địa điểm', {
    exact: true
  }).fill('Hà Nội');
  await recruiter.getByLabel('Mức lương').fill('20–30 triệu');
  const deadline = new Date(Date.now() + 30 * 86400000).toISOString().slice(0, 16);
  await recruiter.getByLabel('Hạn ứng tuyển').fill(deadline);
  await recruiter.getByLabel('Mô tả công việc').fill('Xây dựng các API bằng Python và FastAPI.');
  await recruiter.getByLabel('Yêu cầu ứng viên').fill('Kinh nghiệm Python, React và PostgreSQL.');
  await recruiter.getByRole('button', {
    name: 'Lưu bản nháp'
  }).click();
  await expect(recruiter.getByRole('heading', {
    name: `Python E2E ${suffix}`
  })).toBeVisible();
  await recruiter.getByRole('button', {
    name: 'Đăng tin',
    exact: true
  }).click();
  await expect(recruiter.locator('.badge.Published')).toHaveText('Đang tuyển');
  await register(candidate, 'Candidate', 'Ứng viên E2E');
  await candidate.goto('/profile');
  await candidate.getByLabel('Kỹ năng').fill('Python, React');
  await candidate.getByRole('button', {
    name: 'Lưu hồ sơ'
  }).click();
  await expect(candidate.getByRole('status')).toContainText('Đã lưu hồ sơ cá nhân');
  await candidate.getByLabel('Tên phiên bản').fill('CV browser demo');
  // Real valid one-page PDF built with byte offsets (no application API mocks).
  let pdf = '%PDF-1.4\n';
  const objects = ['<< /Type /Catalog /Pages 2 0 R >>', '<< /Type /Pages /Kids [3 0 R] /Count 1 >>', '<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] >>'];
  const offsets = [0];
  objects.forEach((object, i) => {
    offsets.push(Buffer.byteLength(pdf));
    pdf += `${i + 1} 0 obj\n${object}\nendobj\n`;
  });
  const xref = Buffer.byteLength(pdf);
  pdf += `xref\n0 4\n0000000000 65535 f \n${offsets.slice(1).map(offset => `${String(offset).padStart(10, '0')} 00000 n \n`).join('')}trailer\n<< /Size 4 /Root 1 0 R >>\nstartxref\n${xref}\n%%EOF\n`;
  await candidate.getByLabel('File PDF').setInputFiles({
    name: 'cv.pdf',
    mimeType: 'application/pdf',
    buffer: Buffer.from(pdf)
  });
  await candidate.getByRole('button', {
    name: 'Tải CV lên'
  }).click();
  await expect(candidate.getByText('CV browser demo', {
    exact: true
  })).toBeVisible();
  await candidate.goto('/');
  await candidate.getByRole('textbox', {
    name: 'Từ khóa công việc'
  }).fill(`Python E2E ${suffix}`);
  await candidate.getByRole('button', {
    name: 'Tìm việc',
    exact: true
  }).click();
  await candidate.getByRole('heading', {
    name: `Python E2E ${suffix}`
  }).click();
  await candidate.getByLabel('Lời giới thiệu').fill('Tôi muốn gia nhập đội ngũ và phát triển sản phẩm.');
  await candidate.getByRole('button', {
    name: 'Gửi hồ sơ ứng tuyển'
  }).click();
  await candidate.getByRole('link', {
    name: 'Xem hồ sơ đã nộp'
  }).click();
  await expect(candidate.locator('.badge.Submitted')).toBeVisible();
  const applicationUrl = candidate.url();
  await recruiter.goto('/recruiter');
  await recruiter.getByRole('link', {
    name: '1 hồ sơ'
  }).click();
  await recruiter.getByRole('heading', {
    name: 'Ứng viên E2E'
  }).click();
  const download = recruiter.waitForEvent('download');
  await recruiter.getByRole('button', {
    name: 'Tải CV PDF'
  }).click();
  expect((await download).suggestedFilename()).toBe('JobApply-CV.pdf');
  await recruiter.getByRole('button', {
    name: 'Đang xét',
    exact: true
  }).click();
  await expect(recruiter.locator('.badge.Reviewing')).toBeVisible();
  await candidate.goto(applicationUrl);
  await expect(candidate.locator('.badge.Reviewing')).toBeVisible();
  await expect(candidate.getByText('Đã nộp → Đang xét')).toBeVisible();
  await recruiterContext.close();
  await candidateContext.close();
});
test('search page is responsive, filters work, empty results are explicit', async ({
  page
}) => {
  const errors = [];
  page.on('pageerror', error => errors.push(error.message));
  await page.goto('/');
  await expect(page.getByRole('heading', {
    name: 'Việc làm dành cho bạn.'
  })).toBeVisible();
  await page.screenshot({
    path: 'test-results/home-desktop.png',
    fullPage: true
  });
  await page.setViewportSize({
    width: 390,
    height: 844
  });
  await page.screenshot({
    path: 'test-results/home-mobile.png',
    fullPage: true
  });
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.getByRole('textbox', {
    name: 'Từ khóa công việc'
  }).fill('no-such-job-xyz123');
  await page.getByRole('button', {
    name: 'Tìm việc',
    exact: true
  }).click();
  await expect(page.getByRole('heading', {
    name: 'Chưa tìm thấy cơ hội phù hợp'
  })).toBeVisible();
  await page.getByRole('button', {
    name: 'Đặt lại',
    exact: true
  }).click();
  await page.getByLabel('Từ xa', {
    exact: true
  }).check();
  await expect(page).toHaveURL(/work_mode=Remote/);
  expect(errors).toEqual([]);
});
