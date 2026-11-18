import {test,expect} from '../../e2e/node_modules/@playwright/test/index.mjs';
for(const [role,status,allowed] of [['admin','in_delivery',false],['admin','paid',true],['barista','in_delivery',false]] as const){
test(`${role} ${status} cancel availability`,async({page,context,baseURL},info)=>{
 const order={id:'00000000-0000-4000-8000-000000000088',user_id:'00000000-0000-4000-8000-000000000010',status,type:'delivery',subtotal:30000,discount_amount:0,delivery_fee:0,total:30000,created_at:'2026-11-09T08:00:00Z',items:[],customer_display_name:null,customer_contact_phone:null,payment_status:'succeeded',can_retry_refund:false,payment_resolution:null};
 const errors:string[]=[];page.on('pageerror',e=>errors.push(e.name));
 await context.route('**/*',async route=>{
  const u=new URL(route.request().url());
  if(u.origin!==baseURL)return route.abort();
  if(!u.pathname.startsWith('/api/'))return route.continue();
  if(u.pathname==='/api/v1/staff/auth/refresh')return route.fulfill({json:{access_token:'synthetic-ui-token',token_type:'bearer',role}});
  if(u.pathname==='/api/v1/admin/orders')return route.fulfill({json:{orders:[order],page:1,per_page:20,total_count:1}});
  if(u.pathname===`/api/v1/admin/orders/${order.id}`)return route.fulfill({json:order});
  return route.fulfill({status:404,json:{detail:'unexpected isolated route'}});
 });
 await page.goto('/admin/orders');
 await page.getByTestId(`order-details-${order.id}`).click();
 await expect(page.getByRole('dialog')).toBeVisible();
 await page.screenshot({path:info.outputPath('dialog.png'),fullPage:true});
 await info.attach('ui',{body:await page.locator('body').ariaSnapshot(),contentType:'text/plain'});
 expect(errors).toEqual([]);
 const cancel=page.getByTestId('order-action-cancel');
 if(allowed)await expect(cancel).toBeVisible();
 else await expect(cancel).toHaveCount(0);
});}
