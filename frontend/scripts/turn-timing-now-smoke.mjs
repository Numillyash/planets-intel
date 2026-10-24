import { chromium } from "playwright";
import assert from "node:assert/strict";
import { mkdirSync } from "node:fs";

const output = "/tmp/turn-timing-now-smoke";
mkdirSync(output, { recursive: true });

const samplePlayer=(slot_id,username)=>({
  slot_id, username, race_id:4, current_turn:15, current_state:"ready",
  state_observed_at:null,first_open_observed_at:null,ready_at:null,
  open_samples:3,ready_samples:3,
  open_utc_minutes:[30,180,720],
  ready_utc_minutes:[60,660,1100],
  typical_open_utc_minute:null,typical_ready_utc_minute:null,
  median_open_after_host_minutes:120,median_ready_after_host_minutes:95,
  prediction_confidence:"high",all_current_games_count:2,
  all_current_games_open_samples:3,all_current_games_ready_samples:3,
  all_current_games_open_utc_minutes:[30,180,720],
  all_current_games_ready_utc_minutes:[60,660,1100],
  all_current_games_prediction_confidence:"high",
});
const response={
  game_id:687568,through_turn:15,current_games_considered:2,
  polling_note:"Browser fixture with factual sample positions",
  players:[samplePlayer(1,"alpha"),samplePlayer(2,"beta")],
};

const browser=await chromium.launch({
  headless:true,
  args:["--disable-dev-shm-usage"],
});
const context=await browser.newContext({
  viewport:{width:1460,height:900},
  timezoneId:"Europe/Moscow",
});
const page=await context.newPage();
const errors=[];
page.on("pageerror",e=>errors.push(e.message));
page.on("console",e=>{if(e.type()==="error")errors.push(e.text());});
await page.route("**/api/games/687568/activity*",route=>route.fulfill({
  status:200,contentType:"application/json",body:JSON.stringify(response),
}));
const assertMarkers=async (local,utc)=>{
  await page.getByTestId("turn-timing-now-clock").waitFor({state:"visible"});
  const header=await page.getByTestId("turn-timing-now-clock").innerText();
  assert(header.includes("NOW") && header.includes(local+" local")
    && header.includes(utc+" UTC"),"Wrong clock header: "+header);
  const marker=page.locator(".turn-timing-now-line");
  const labels=page.locator(".turn-timing-now-label");
  assert.equal(await marker.count(),4,"Every chart must have its own live marker");
  assert.equal(await labels.count(),4,"Every chart must visibly say NOW");
  const positions=await marker.evaluateAll(els=>els.map(el=>Number(el.getAttribute("x1"))));
  assert(positions.every(x=>Math.abs(x-positions[0])<0.001),
    "Four charts disagree about what time it is: "+positions);
  const expectedLocalMinute=Number(local.slice(0,2))*60+Number(local.slice(3));
  const expectedX=expectedLocalMinute*300/1440;
  assert(Math.abs(positions[0]-expectedX)<0.25,
    "NOW line position does not match local time: "+positions[0]+" expected "+expectedX);
  // SVG <title> does not expose innerText in Chromium; read textContent.
  const titles=await page.locator(".turn-timing-density-svg title")
    .evaluateAll(nodes=>nodes.map(node=>node.textContent??""));
  assert.equal(titles.length,4);
  assert(titles.every(t=>t.includes(local+" local")&&t.includes(utc+" UTC")
    &&t.includes("not the mean")),"SVG tooltips missing time context: "+titles);
  return positions[0];
};
try {
  await page.clock.install({time:new Date("2026-10-24T13:41:00.000Z")});
  await page.goto("http://127.0.0.1:4173/test/turn-timing-marker.html",{
    waitUntil:"networkidle",timeout:30000,
  });
  const before=await assertMarkers("16:41","13:41");
  await page.screenshot({path:output+"/desktop-now.png",fullPage:true});
  console.log("PASS: current time label and identical marker positions in 4 real charts",before);

  await page.clock.fastForward(2*60*1000);
  const after=await assertMarkers("16:43","13:43");
  assert(after>before,"NOW marker did not advance when time advanced");
  console.log("PASS: NOW label and all chart lines advance automatically",before,after);

  await page.setViewportSize({width:390,height:844});
  await page.screenshot({path:output+"/mobile-now.png",fullPage:true});
  const labels=await page.locator(".turn-timing-now-label").allTextContents();
  assert(labels.every(t=>t==="NOW"),"Mobile marker labels must remain visible");
  assert.equal(errors.length,0,"Browser JS errors: "+errors.join("\n"));
  console.log("PASS: responsive browser capture, no JS errors");
} catch(e){
  await page.screenshot({path:output+"/failure.png",fullPage:true}).catch(()=>{});
  console.error("TURN_TIMING_NOW_SMOKE_FAILED",e,errors);
  process.exitCode=1;
} finally {
  await browser.close();
}
