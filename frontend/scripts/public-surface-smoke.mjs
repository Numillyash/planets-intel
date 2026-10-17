import { chromium } from "playwright";
import { PNG } from "pngjs";
import assert from "node:assert/strict";
import { mkdirSync } from "node:fs";

const base = "http://127.0.0.1:4173";
const archived = {
  mode:"public_finished_archive",
  source:"planets.nu/game/loadturn",
  game_id:683230, player_slot_id:4, turn:54,
  counts:{planets:3,ships:1,starbases:1},
  planets:[
    {planet_id:1,owner_id:4,info_turn:54,name:"Alpha",x:1140,y:1000,payload:{id:1,clans:200,mines:10}},
    {planet_id:2,owner_id:null,info_turn:54,name:"Beta",x:1400,y:1260,payload:{id:2}},
    {planet_id:3,owner_id:2,info_turn:54,name:"Gamma",x:1660,y:1120,payload:{id:3}},
  ],
  ships:[{ship_id:11,owner_id:4,info_turn:54,hull_id:5,name:"Scout",
    x:1140,y:1000,warp:7,payload:{id:11,warp:7}}],
  starbases:[{starbase_id:1,planet_id:1,race_id:4,info_turn:54,payload:{id:1}}],
  stellar_cartography:[],
};
const game = {
  source:"public",game:{
    id:683230,name:"Org ania test",short_description:"Read-only public sector",
    description:"",status_id:3,status_name:"Finished",turn:54,slots:9,
    turn_status:null,next_host:"",turns_per_week:null,is_private:false,
    is_custom:false,win_condition_id:null,
  },
  settings:{turn:54,map_width:2000,map_height:2000,num_planets:3},
  players:[{
    slot_id:4,account_id:4,username:"archival pilot",race_id:4,status:1,
    turn_status:null,turns_missed:0,planets:1,ships:1,starbases:1,
    turn_ready:null,active_advantages:"",active_hulls:"",
  }],
  relations:[],schedule:"",time_to_host:"",year_from:"",year_to:"",win_condition:"",
};
const errors=[];
const calls=[];
const browser=await chromium.launch({
  headless:true,
  args:["--enable-webgl","--use-gl=angle","--use-angle=swiftshader","--disable-dev-shm-usage"],
});
const context=await browser.newContext({viewport:{width:1440,height:900},deviceScaleFactor:1});
const page=await context.newPage();
page.on("pageerror",e=>errors.push(e.message));
page.on("console",e=>{
  // A missing optional scores cache legitimately returns HTTP 404.
  // Actual render exceptions are captured by pageerror above.
  if(e.type()==="error" && !e.text().includes("Failed to load resource: the server responded with a status of 404")) {
    errors.push("console: "+e.text());
  }
});
await page.route("**/*",async route=>{
  const url=new URL(route.request().url());
  // Vite's source imports include /src/api/client.ts: never intercept those.
  if(!url.pathname.startsWith("/api/")) return route.continue();
  calls.push(url.pathname);
  let status=200,body;
  if(url.pathname==="/api/auth/me") body={id:7,username:"tester",display_name:"Smoke tester"};
  else if(url.pathname==="/api/games/683230") body=game;
  else if(url.pathname==="/api/games/683230/scores/history") {
    status=404;body={detail:"not collected"};
  } else if(url.pathname==="/api/games/683230/public-commander-intelligence") {
    body={
      game_id:683230,method_version:"test",commanders:[],pairwise:[],
      public_timeline:{
        status:"available",eligible_event_count:2,skipped_event_rows:0,
        truncated:false,provenance:{
          source:"planets.nu/game/loadinfo",cache_state:"fresh",fetched_at:null,
        },
        events:[
          {event_id:1,turn:54,event_type:6,slot_id:4,
            description:"Public victory event",date_added:"9/27/2026 3:53:46 PM"},
          {event_id:2,turn:1,event_type:3,slot_id:4,
            description:"Join event without date",date_added:null},
        ],
      },
    };
  } else if(url.pathname==="/api/games/683230/public-archive/turn") body=archived;
  else {status=404;body={detail:"not available in smoke"};}
  await route.fulfill({status,contentType:"application/json",body:JSON.stringify(body)});
});
const load=async url=>{
  await page.goto(base+url,{waitUntil:"networkidle",timeout:30000});
  await page.waitForTimeout(400);
};
const visible=async selector=>{
  const l=page.locator(selector).first();
  await l.waitFor({state:"visible",timeout:12000});
  assert(await l.isVisible(),selector+" is not visible");
};
const noErrors=()=>assert.equal(errors.length,0,"JS runtime errors: "+errors.join("\n"));

try{
  await load("/intelboard/public/683230?slot=4&turn=54&view=dashboard&tab=dashboard");
  await visible(".game-dashboard-shell");
  await visible(".global-page-nav-slot > .public-game-navigation");
  assert.equal(await page.locator(".game-dashboard-tabs button").count(),17,
    "Public dashboard must share the native game section strip");
  assert.equal(await page.locator(".game-dashboard-summary .summary-card").count(),6,
    "Public dashboard must share the six-card native overview");
  assert.equal(await page.locator(".game-dashboard-launch-grid button").count(),16,
    "Public dashboard must share the native section launcher");
  assert.equal(await page.locator(".public-archive-observer-selectors .summary-card").count(),2,
    "The public header must use native Observer and Game selectors");
  assert.equal(await page.locator(".app-shell > .public-game-navigation").count(),0,
    "Do not duplicate the global game navigation above the tab strip");
  await page.screenshot({path:"/tmp/public-surface-smoke/dashboard.png"}).catch(()=>{});
  console.log("PASS: native dashboard layout parity - 17 tabs, six summary cards, 16 launch tiles");
  await page.locator(".game-dashboard-tabs")
    .getByRole("button",{name:"Commander intel",exact:true}).click();
  await visible(".commander-public-timeline");
  const timeline=await page.locator(".commander-public-timeline").innerText();
  assert(timeline.includes("recorded 9/27/2026 3:53:46 PM (source time)"),
    "Source event time not displayed: "+timeline);
  assert(timeline.includes("time not provided"),"Unknown event time must stay unknown");
  assert(timeline.includes("does not specify a timezone"),
    "Source timezone limitation must be visible");
  console.log("PASS: public event timestamp is source-backed and missing time stays unknown");
  await page.locator(".game-dashboard-tabs")
    .getByRole("button",{name:"Dashboard",exact:true}).click();
  // Each native object tab owns its table. There is no second object-type
  // selector which could disagree with the selected tab.
  for (const [tab, heading, rows] of [
    ["Planets", "Planet List", 3],
    ["Starships", "Starship List", 1],
    ["Starbases", "Starbase List", 1],
  ]) {
    await page.locator(".game-dashboard-tabs").getByRole("button",{name:tab,exact:true}).click();
    await visible(".game-object-table");
    const title=await page.locator(".game-dashboard-content .panel-header h2").first().innerText();
    assert(title.includes(heading),`Wrong ${tab} panel: ${title}`);
    assert.equal(await page.locator(".game-object-table tbody tr").count(),rows,`Wrong ${tab} count`);
    assert.equal(await page.getByLabel("Object type").count(),0,
      `Redundant selector must not appear on ${tab}`);
  }
  // Backwards compatibility: former tab=objects renders Planets, not a stale
  // object-type dropdown or unrelated overview.
  await load("/intelboard/public/683230?slot=4&turn=54&view=dashboard&tab=objects");
  await visible(".game-object-table");
  assert((await page.locator(".game-dashboard-content .panel-header h2").first().innerText()).includes("Planet List"));
  assert.equal(await page.getByLabel("Object type").count(),0);
  console.log("PASS: Planets / Starships / Starbases tables have fixed native types and no redundant selector");
  await page.locator(".game-dashboard-tabs").getByRole("button",{name:"Dashboard",exact:true}).click();
  assert.equal(await page.locator(".intel-map-panel").count(),0,"Map must not mount inside Dashboard");
  await page.locator(".global-page-nav-slot > .public-game-navigation")
    .getByRole("button",{name:"Starmap"}).click();
  await visible(".app-shell > .intel-map-panel");
  await visible(".intel-map-canvas-host canvas");
  const mapState=await page.evaluate(()=>{
    const map=document.querySelector(".app-shell > .intel-map-panel");
    const canvas=map?.querySelector("canvas");
    if(!map||!canvas) return null;
    const box=canvas.getBoundingClientRect();
    const panel=map.getBoundingClientRect();
    return {canvasWidth:box.width,canvasHeight:box.height,
      panelWidth:panel.width,panelHeight:panel.height,
      mapDisplay:getComputedStyle(map).display,
      mapVisibility:getComputedStyle(map).visibility,
      mapParent:map.parentElement?.className,
      navVisible:!!map.querySelector(".public-game-navigation.is-map")};
  });
  assert(mapState,"No map surface");
  assert(mapState.canvasWidth>300&&mapState.canvasHeight>300,
    "Canvas must have nonzero visible dimensions "+JSON.stringify(mapState));
  assert(mapState.panelHeight>500 && mapState.navVisible,
    "Operational map or its navigation is missing "+JSON.stringify(mapState));
  assert(!String(mapState.mapDisplay).includes("none"));
  // A visible WebGL canvas can still be an empty dark rectangle: sample its
  // screenshot without changing the application's WebGL context.
  await page.waitForTimeout(300);
  const canvasPng=PNG.sync.read(await page.locator(".intel-map-canvas-host canvas").screenshot());
  let brightPixels=0;
  for(let y=0;y<canvasPng.height;y+=3) {
    for(let x=0;x<canvasPng.width;x+=3) {
      const p=(y*canvasPng.width+x)*4;
      const [red,green,blue,alpha]=canvasPng.data.subarray(p,p+4);
      if(alpha>0 && (red>120 || green>75 || blue>100)) brightPixels++;
    }
  }
  assert(brightPixels>40,`Map has no visibly drawn objects (bright sampled pixels: ${brightPixels})`);
  console.log("PASS: non-empty Pixi map drawing",brightPixels,"sampled bright pixels");
  mkdirSync("/tmp/public-surface-smoke",{recursive:true});
  await page.screenshot({path:"/tmp/public-surface-smoke/map.png"});
  console.log("PASS: fullscreen operational map",JSON.stringify(mapState));

  await page.locator(".public-game-navigation.is-map")
    .getByRole("button",{name:"Dashboard"}).click();
  await visible(".game-dashboard-shell");
  assert.equal(await page.locator(".intel-map-panel").count(),0);
  await page.locator(".global-page-nav-slot > .public-game-navigation")
    .getByRole("button",{name:/Turn 54/}).click();
  await visible(".public-archive-time-machine");
  await page.screenshot({path:"/tmp/public-surface-smoke/time-machine.png"});
  console.log("PASS: map to dashboard to time-machine navigation");

  await load("/intelboard/public/683230?slot=4&turn=54&view=dashboard&tab=starmap");
  await visible(".app-shell > .intel-map-panel");
  console.log("PASS: old deep links retain accessible map");
  const privateHits=calls.filter(x=>/private-intel|linked-account|order-drafts|movement-prediction|historical-ship-tracks/.test(x));
  assert.equal(privateHits.length,0,"Archive must not call private endpoints: "+privateHits);
  noErrors();
  console.log("PASS: no runtime errors, no private observer API requests");
} catch(e){
  mkdirSync("/tmp/public-surface-smoke",{recursive:true});
  await page.screenshot({path:"/tmp/public-surface-smoke/failure.png"}).catch(()=>{});
  console.error("BROWSER_SMOKE_FAILED:",e);
  console.error("Page errors:",errors);
  console.error("API paths:",calls);
  process.exitCode=1;
} finally {
  await browser.close();
}
