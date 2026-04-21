import { chromium } from 'playwright';

const BASE = 'http://localhost:5173';

(async () => {
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage();

  function log(msg) { console.log(msg); }

  try {
    // 1. Load the dashboard
    log('--- TEST 1: Dashboard loads ---');
    await page.goto(BASE, { waitUntil: 'networkidle', timeout: 60000 });
    log(`  Page title: "${await page.title()}"`);

    // 2. Sidebar
    log('\n--- TEST 2: Sidebar ---');
    log(`  Sidebar: ${!!(await page.$('.sidebar'))}`);

    // 3. Campaign tab (default)
    log('\n--- TEST 3: Campaign tab ---');
    await page.waitForSelector('.data-table', { timeout: 90000 });
    const kpis = await page.$$eval('.kpi-card', cards =>
      cards.map(c => `${c.querySelector('.kpi-label')?.textContent}: ${c.querySelector('.kpi-value')?.textContent}`)
    );
    kpis.forEach(k => log(`  ${k}`));

    const headers = await page.$$eval('.data-table thead th', ths => ths.map(th => th.textContent.trim()));
    log(`  Columns: ${headers.join(', ')}`);
    log(`  Rows: ${(await page.$$('.data-table tbody tr')).length}`);

    const sections = await page.$$eval('h2', els => els.map(e => e.textContent));
    log(`  Sections: ${sections.join(' | ')}`);

    // 4. Find and click tab buttons
    log('\n--- TEST 4: Tab navigation ---');
    // Find all clickable tab elements
    const tabTexts = await page.$$eval('[class*="tab"]', els => els.map(e => `${e.tagName}.${e.className}: "${e.textContent.trim().substring(0,30)}"`));
    log(`  Tab-like elements: ${tabTexts.length}`);
    tabTexts.forEach(t => log(`    ${t}`));

    // Try to find tabs by text content
    const keywordTab = await page.$('text=Keywords');
    const searchTab = await page.$('text=Search Terms');
    const chatTab = await page.$('text=Ask AI');

    if (keywordTab) {
      log('\n--- TEST 5: Keyword tab ---');
      await keywordTab.click();
      await page.waitForTimeout(3000);
      try { await page.waitForSelector('.data-table', { timeout: 60000 }); } catch(e) {}
      await page.waitForTimeout(3000);
      const kwRows = await page.$$('.data-table tbody tr');
      log(`  Keyword rows: ${kwRows.length}`);
      const kwHeaders = await page.$$eval('.data-table thead th', ths => ths.map(th => th.textContent.trim()));
      log(`  Columns: ${kwHeaders.join(', ')}`);
    } else {
      log('\n  Keywords tab not found');
    }

    if (searchTab) {
      log('\n--- TEST 6: Search Terms tab ---');
      await searchTab.click();
      await page.waitForTimeout(3000);
      try { await page.waitForSelector('.data-table', { timeout: 60000 }); } catch(e) {}
      await page.waitForTimeout(3000);
      const stRows = await page.$$('.data-table tbody tr');
      log(`  Search term rows: ${stRows.length}`);
    } else {
      log('\n  Search Terms tab not found');
    }

    // 7. Region filter - go back to campaigns first
    log('\n--- TEST 7: Region filter (India) ---');
    const campTab = await page.$('text=Campaigns');
    if (campTab) await campTab.click();
    await page.waitForTimeout(2000);

    const indiaLabel = await page.$('label:has-text("India")');
    if (indiaLabel) {
      await indiaLabel.click();
      await page.waitForTimeout(5000);
      try { await page.waitForSelector('.data-table', { timeout: 60000 }); } catch(e) {}
      await page.waitForTimeout(2000);
      const names = await page.$$eval('.data-table tbody tr td:first-child', tds => tds.map(td => td.textContent));
      log(`  India campaigns (${names.length}): ${names.join(', ')}`);
      const hasUS = names.some(n => n.startsWith('US-'));
      log(`  Contains US campaigns: ${hasUS} (should be false)`);
    }

    // 8. Region filter US
    log('\n--- TEST 8: Region filter (US) ---');
    const usLabel = await page.$('label:has-text("US")');
    if (usLabel) {
      await usLabel.click();
      await page.waitForTimeout(5000);
      try { await page.waitForSelector('.data-table', { timeout: 60000 }); } catch(e) {}
      await page.waitForTimeout(2000);
      const names = await page.$$eval('.data-table tbody tr td:first-child', tds => tds.map(td => td.textContent));
      log(`  US campaigns (${names.length}): ${names.join(', ')}`);
      const hasIND = names.some(n => n.startsWith('IND-') || n.startsWith('Ind_') || n.startsWith('Ind-'));
      log(`  Contains India campaigns: ${hasIND} (should be false)`);
    }

    // Screenshot
    log('\n--- TEST 9: Screenshot ---');
    // Go back to All + Campaigns
    const allLabel = await page.$('label:has-text("All")');
    if (allLabel) await allLabel.click();
    await page.waitForTimeout(5000);
    try { await page.waitForSelector('.data-table', { timeout: 60000 }); } catch(e) {}
    await page.waitForTimeout(3000);
    await page.screenshot({ path: '/Users/sakshibatavia/google-ads-analysis/dashboard-screenshot.png', fullPage: true });
    log('  Screenshot saved');

    log('\n=== ALL TESTS COMPLETE ===');
  } catch (err) {
    log(`\nERROR: ${err.message}`);
    await page.screenshot({ path: '/Users/sakshibatavia/google-ads-analysis/error-screenshot.png' }).catch(() => {});
  } finally {
    await browser.close();
  }
})();
