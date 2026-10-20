import { chromium } from "playwright";
import { readFileSync, mkdirSync, writeFileSync } from "node:fs";
import assert from "node:assert/strict";

const file = process.env.PUBLIC_VISUAL_RST ?? "/tmp/planets-public-visual-rst.json";
const archive = JSON.parse(readFileSync(file,"utf8"));
assert.equal(archive.mode,"public_finished_archive");
assert.equal(archive.source,"planets.nu/game/loadturn");
const {game_id:gameId,player_slot_id:slot,turn} = archive;
const root="/tmp/planets-public-visual-evidence";
mkdirSync(root,{recursive:true});
const errors=[],apiCalls=[];
const game={
  source:"public",
  game:{id:gameId,name:"Public sector #"+gameId,
    short_description:"Public finished RST - rendered from actual Planets.nu data",
    description:"",status_id:3,status_name:"Finished",turn,
    slots:12,turn_status:null,next_host:"",turns_per_week:null,
    is_private:false,is_custom:false,win_condition_id:null},
  settings:{turn,map_width:4000,map_height:4000,num_planets:archive.planets.length},
  players:[{slot_id:slot,account_id:slot,username:"Public slot #"+slot,
    race_id:4,status:1,turn_status:null,turns_missed:0,
    planets:archive.planets.length,ships:archive.ships.length,
    starbases:archive.starbases.length,turn_ready:null,
    active_advantages:"",active_hulls:""}],
  relations:[],schedule:"",time_to_host:"",year_from:"",year_to:"",
  win_condition:"",
};
const browser=await chromium.launch({headless:true,
  args:["--enable-webgl","--use-gl=angle","--use-angle=swiftshader",
    "--disable-dev-shm-usage"]});
const page=await browser.newPage({viewport:{width:1600,height:950},deviceScaleFactor:1});
page.on("pageerror",e=>errors.push(e.stack??e.message));
page.on("console",e=>{
  if(e.type()==="error" && !e.text().includes("Failed to load resource: the server responded with a status of 404")) errors.push(e.text());
});
await page.route("**/*",async route=>{
  const url=new URL(route.request().url());
  if(!url.pathname.startsWith("/api/")) return route.continue();
  apiCalls.push(url.pathname);
  let data,status=200;
  if(url.pathname==="/api/auth/me") data={id:7,username:"visual-fixture",display_name:"Public visual fixture"};
  else if(url.pathname===`/api/games/${gameId}`) data=game;
  else if(url.pathname===`/api/games/${gameId}/public-archive/turn`) data=archive;
  else {status=404;data={detail:"Not present in public-only fixture"};}
  await route.fulfill({status,contentType:"application/json",body:JSON.stringify(data)});
});
try{
  await page.goto(`http://127.0.0.1:4173/intelboard/public/${gameId}?slot=${slot}&turn=${turn}&view=starmap`,{waitUntil:"networkidle",timeout:45000});
  await page.locator(".app-shell > .intel-map-panel canvas").waitFor({state:"visible",timeout:18000});
  await page.waitForTimeout(1000);
  const summary=await page.evaluate(async({archive,slot})=>{
    const {showForeignPlanetSurveyRing,hasPlanetSurveyEvidence}=
      await import("/src/features/map/planetSurveyMarker.ts");
    const buckets={own:0,foreign:0,unknown:0};
    const surveyed={own:0,foreign:0,unknown:0};
    const infoTurnPresent={own:0,foreign:0,unknown:0};
    const examples=[];
    for(const p of archive.planets){
      const group=p.owner_id===slot?"own":p.owner_id===null?"unknown":"foreign";
      buckets[group]++;
      if(p.info_turn!==null&&p.info_turn>0) infoTurnPresent[group]++;
      if(hasPlanetSurveyEvidence(p)) surveyed[group]++;
      if(showForeignPlanetSurveyRing(p,slot)&&examples.length<15)
        examples.push({planet_id:p.planet_id,owner_id:p.owner_id,info_turn:p.info_turn});
    }
    const el=document.querySelector(".app-shell > .intel-map-panel");
    const c=el?.querySelector("canvas");
    const b=c?.getBoundingClientRect();
    return {game_id:archive.game_id,slot,turn:archive.turn,
      planets:archive.planets.length,ships:archive.ships.length,
      starbases:archive.starbases.length,buckets,surveyed,infoTurnPresent,
      examples,canvas:{width:b?.width,height:b?.height}};
  },{archive,slot});
  assert(summary.canvas.width>600 && summary.canvas.height>400,"Map is not visible");
  await page.screenshot({path:root+"/public-real-rst-map.png",fullPage:false});
  await page.locator(".app-shell > .intel-map-panel canvas").screenshot({
    path:root+"/public-real-rst-canvas.png"});
  writeFileSync(root+"/summary.json",JSON.stringify(summary,null,2));
  assert.equal(errors.length,0,"Runtime errors: "+errors.join("\n"));
  assert(!apiCalls.some(x=>/private-intel|draft|linked-account|movement-prediction/.test(x)),
    "Public screenshot invoked private endpoint");
  console.log("PASS REAL PUBLIC RST BROWSER IMAGE:",JSON.stringify(summary));
} catch(e){
  await page.screenshot({path:root+"/failure.png"}).catch(()=>{});
  console.error(e);
  console.error("runtime errors",errors);
  process.exitCode=1;
} finally {await browser.close();}
