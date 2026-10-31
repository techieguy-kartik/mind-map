import {test,expect} from '@playwright/test';

test('overview, company filter, evidence navigation and export',async({page})=>{
  const errors:string[]=[];page.on('pageerror',e=>errors.push(e.message));
  await page.goto('/');
  await expect(page.getByRole('heading',{name:'See the signal. Understand the move.'})).toBeVisible();
  await expect(page.getByText('Companies are real; events, graph connections, and hypotheses are fictional examples.')).toBeVisible();
  await page.getByRole('button',{name:'Companies',exact:true}).click();
  await page.getByRole('textbox',{name:'Search workspace'}).fill('Reliance');
  await expect.poll(()=>page.locator('.company-row').count()).toBeGreaterThanOrEqual(2);
  await page.getByRole('button',{name:'RI Reliance Industries Reliance ecosystem'}).click();
  await expect(page.getByRole('dialog')).toContainText('Financial qualification');
  await page.keyboard.press('Escape');
  const downloadPromise=page.waitForEvent('download');await page.getByRole('button',{name:'Export',exact:true}).click();
  expect((await downloadPromise).suggestedFilename()).toBe('atlas-evidence-export.json');
  expect(errors).toEqual([]);
});

test('registry sector coverage and pagination are usable',async({page})=>{
  await page.goto('/');
  await page.getByRole('button',{name:'Companies',exact:true}).click();
  await page.getByRole('combobox',{name:'Sector filter'}).selectOption('AI & Machine Learning');
  await expect(page.locator('.company-row')).toHaveCount(50);
  await expect(page.locator('.registry-coverage')).toContainText('100 candidates');
  await page.getByRole('button',{name:'Next',exact:true}).click();
  await expect(page.getByText('Page 2',{exact:true})).toBeVisible();
  await expect(page.locator('.company-row')).toHaveCount(50);
});

test('server changes update the browser through the live stream',async({page})=>{
  await page.goto('/');
  await page.getByRole('button',{name:'Companies',exact:true}).click();
  await page.getByRole('textbox',{name:'Search workspace'}).fill('Tesla');
  await page.request.put('/api/watchlist/tesla',{data:{watched:false}});
  await expect(page.getByRole('button',{name:'Watch Tesla',exact:true})).toBeVisible({timeout:8000});
  await page.request.put('/api/watchlist/tesla',{data:{watched:true}});
  await expect(page.getByRole('button',{name:'Unwatch Tesla',exact:true})).toBeVisible({timeout:8000});
});

test('watchlist survives reload',async({page})=>{
  await page.goto('/');await page.getByRole('button',{name:'Companies',exact:true}).click();
  const add=page.getByRole('button',{name:'Watch Tesla',exact:true});
  if(await add.count())await add.click();
  await expect(page.getByRole('button',{name:'Unwatch Tesla',exact:true})).toBeVisible();
  await page.reload();await page.getByRole('button',{name:/^Watchlist/}).click();
  await expect(page.locator('.company-row').filter({hasText:'Tesla'})).toHaveCount(1);
});

test('graph interaction opens its supporting event',async({page})=>{
  await page.goto('/');await page.getByRole('button',{name:'Intelligence graph',exact:true}).click();
  await page.getByRole('button',{name:'Select Jio Platforms',exact:true}).click();
  await page.getByRole('button',{name:'Open Jio Platforms',exact:true}).click();
  await expect(page.getByRole('dialog')).toContainText('Connected developments');
  await page.keyboard.press('Escape');
  await page.getByRole('button',{name:/Inspect scenario connection/}).first().click();
  await expect(page.getByRole('dialog')).toContainText('Evidence ledger');
  await expect(page.getByRole('dialog')).toContainText('Synthetic example');
});

test('investigation without a key returns an honest persisted inventory',async({page})=>{
  await page.goto('/');await page.getByRole('button',{name:'New investigation',exact:true}).click();
  await page.getByRole('button',{name:'Start investigation',exact:true}).click();
  await expect(page.getByRole('dialog')).toContainText('no AI synthesis was performed',{timeout:10000});
  await page.reload();await page.getByRole('button',{name:'Investigations',exact:true}).click();
  await expect(page.locator('.job-card').first()).toContainText('What changed');
});

test('reviewed evidence creates real graph without mixing demo events',async({page})=>{
  await page.goto('/');await page.getByRole('button',{name:'Intelligence graph',exact:true}).click();
  await page.getByRole('button',{name:'Add evidence'}).click();
  await page.getByLabel('Evidence statement').fill('Browser test fixture only. This is not a verified real-world corporate relationship.');
  await page.getByLabel('Original source URL').fill('https://example.org/browser-test');
  await page.getByLabel('Publisher',{exact:true}).fill('Test fixture');
  await page.getByLabel('Effective date').fill('2026-01-01');
  await page.getByRole('checkbox').check();await page.getByRole('button',{name:'Save reviewed relationship'}).click();
  await expect(page.getByText('Collected headlines are reporting leads.')).toBeVisible();
  await expect(page.getByRole('button',{name:/Inspect subsidiary_of/})).toBeVisible();
});

test('source failure is visible without claiming successful collection',async({page})=>{
  await page.route('**/api/sources/gdelt/sync',route=>route.fulfill({status:200,contentType:'application/json',body:JSON.stringify({status:'Error',error:'Test source unavailable'})}));
  await page.goto('/');await page.getByRole('button',{name:'Sources & coverage',exact:true}).click();
  await page.getByRole('button',{name:'Collect headlines'}).click();
  await expect(page.getByRole('status')).toContainText('Test source unavailable');
  await expect(page.getByText('Durable ingestion')).toBeVisible();
});

test('mobile navigation and layout fit the viewport',async({page})=>{
  await page.setViewportSize({width:390,height:844});await page.goto('/');
  await page.getByRole('button',{name:'Open navigation'}).click();
  await page.getByRole('button',{name:'Strategy radar',exact:true}).click();
  await expect(page.getByRole('heading',{name:'Strategy radar',exact:true})).toBeVisible();
  await page.waitForTimeout(250);
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
  await page.screenshot({path:'test-results/mobile.png',fullPage:true});
});

test('desktop screenshot',async({page})=>{
  await page.setViewportSize({width:1440,height:1050});await page.goto('/');
  await expect(page.locator('.stats')).toBeVisible();
  await page.screenshot({path:'test-results/desktop.png',fullPage:true});
});

test('reviewed financial evidence qualifies a company and monitoring rules persist',async({page})=>{
  await page.goto('/');
  await page.getByRole('button',{name:'Companies',exact:true}).click();
  await page.getByRole('textbox',{name:'Search workspace'}).fill('Jio Platforms');
  await page.locator('.company-name').filter({hasText:'Jio Platforms'}).first().click();
  const dialog=page.getByRole('dialog');
  await dialog.getByText('Record reviewed financial evidence',{exact:true}).click();
  const financial=dialog.locator('form').filter({has:page.getByRole('button',{name:'Save financial evidence'})});
  await financial.getByRole('combobox',{name:'Metric',exact:true}).selectOption('valuation');
  await financial.getByLabel('Amount in original currency').fill('800000000');
  await financial.getByLabel('As-of / annual period end').fill(new Date().toISOString().slice(0,10));
  await financial.getByLabel('Source URL',{exact:true}).fill('https://example.org/browser-fixture-valuation');
  await financial.getByLabel('Publisher',{exact:true}).fill('Browser test fixture');
  await financial.getByRole('checkbox').check();
  await financial.getByRole('button',{name:'Save financial evidence'}).click();
  await expect(dialog.getByRole('heading',{name:'Financial qualification · qualified',exact:true})).toBeVisible();
  await dialog.getByLabel('Priority (1–5)',{exact:true}).fill('5');
  await dialog.getByLabel('Desired check interval').selectOption('900');
  await dialog.getByRole('button',{name:'Save monitoring rules'}).click();
  await expect(dialog.getByRole('status')).toContainText('Watch rules saved');
  const rule=await page.request.get('/api/entities/jio/dossier');
  expect((await rule.json()).watch_rule).toMatchObject({priority:5,interval_seconds:900});
  await page.keyboard.press('Escape');
  await expect(page.locator('.company-row').filter({hasText:'Jio Platforms'}).first()).toContainText('Qualified by recorded evidence');
});

test('people page creates a sourced public profile',async({page})=>{
  await page.goto('/');
  await page.getByRole('button',{name:'People & capital',exact:true}).click();
  await page.getByText('Add a sourced person, fund, trust or company',{exact:true}).click();
  const form=page.locator('form').filter({has:page.getByRole('button',{name:'Create entity'})});
  const name='Browser fixture person '+Date.now();
  await form.getByLabel('Name',{exact:true}).fill(name);
  await form.getByLabel('Country',{exact:true}).fill('India');
  await form.getByLabel('Sector / professional domain').fill('Research');
  await form.getByLabel('Public source URL').fill('https://example.org/browser-fixture-profile');
  await form.getByLabel('Precisely sourced description').fill('Test-only public professional profile fixture.');
  await form.getByRole('button',{name:'Create entity'}).click();
  await page.getByRole('button',{name:new RegExp(name)}).click();
  await expect(page.getByRole('dialog')).toContainText('People, ownership & relationships');
});

test('official source collection sends the selected company and disclosure feed',async({page})=>{
  await page.route('**/api/sources/india-filings/primary-sync',async route=>{
    expect(route.request().postDataJSON()).toEqual({entity_id:'jio',feed:'ownership'});
    await route.fulfill({status:200,contentType:'application/json',body:JSON.stringify({status:'Healthy',inserted:2})});
  });
  await page.goto('/');
  await page.getByRole('button',{name:'Sources & coverage',exact:true}).click();
  await page.getByLabel('NSE disclosure feed').selectOption('ownership');
  await page.locator('.source-card').filter({hasText:'India company disclosures'}).getByRole('button',{name:'Collect official records'}).click();
  await expect(page.getByRole('status')).toContainText('Collected 2 official records');
});
