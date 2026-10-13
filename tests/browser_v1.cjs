const fs = require('node:fs');
const vm = require('node:vm');
const assert = require('node:assert/strict');
class Element {
  constructor() {
    this.value = ''; this.children = []; this.dataset = {}; this.style = {}; this.events = {};
    this.className = ''; this.classList = {add(){},remove(){}};
    this.clientWidth = 600; this.clientHeight = 313; this.scrollLeft = 0; this.scrollTop = 0;
    this.nextElementSibling = {textContent:''}; this.attributes = {}; this.checked = false;
  }
  append(...children) { this.children.push(...children); }
  replaceChildren(...children) { this.children = children.flatMap(x => x.children || [x]); }
  setAttribute(key,val) { this.attributes[key]=val; }
  addEventListener(key,fn) { this.events[key]=fn; }
  querySelector(selector) {return selector === ".active" ? null : new Element();}
  getContext() {return new Proxy({}, {get:()=>()=>{}});}
  getBoundingClientRect() {return {left:0,top:0,width:this.clientWidth,height:this.clientHeight};}
  focus(){}
  scrollIntoView(){}
}
const elements = new Map();
const element = id => {if(!elements.has(id)) elements.set(id,new Element());return elements.get(id);};
const document = {getElementById:element,createElement:()=>new Element(),createDocumentFragment:()=>new Element(),createTextNode:x=>({textContent:x}),addEventListener(){}};
const context = vm.createContext({document,window:{devicePixelRatio:1},ResizeObserver:class {observe(){}},cancelAnimationFrame(){},requestAnimationFrame(){},setTimeout,clearTimeout,console,Map,Set,JSON,Promise,URL,Event:class {}});
vm.runInContext(fs.readFileSync('src/sonata/web/app.js','utf8').replace(/\ninitialize\(\);\s*$/, '\n'),context);
const run = js => vm.runInContext(js,context);
const plain = value => JSON.parse(JSON.stringify(value));
element('palette').value='classical';element('mapping').value='semantic';
element('fixtures').value='[9007199254740993]';element('range-name').value='';
assert.equal(run('requestSettings().inputs_json'),'[9007199254740993]', 'fixture precision must survive transport');
assert.equal(run('requestSettings().profile.mapping'),'semantic');
assert.equal(run('requestSettings().profile.functions'),null);
element('filter-functions').value='fib, main, fib';
assert.deepEqual(plain(run('requestSettings().profile.functions')),['fib','main']);
element('range-name').value='total';element('range-min').value='0';element('range-max').value='10';
assert.deepEqual(plain(run('requestSettings().profile.ranges')),{total:[0,10]});
element('range-max').value='9007199254740993';
assert.throws(()=>run('requestSettings()'), /safe integer/i);
element('range-name').value='';
run('state.total=8; state.cursor=2');element('loop-start').value='1';element('loop-end').value='3';element('loop-enabled').checked=true;
run('readLoop()');assert.deepEqual(plain(run('state.loop')),{enabled:true,start:1,end:3});
element('loop-end').value='0.5';assert.throws(()=>run('readLoop()'),/after/i);
run("state.scoreTokens=['return','15',';'];state.scoreSelection=1;state.scoreDirty=false");
element('token-text').value='10';run("editToken('replace')");assert.deepEqual(plain(run('state.scoreTokens')),['return','10',';']);assert.equal(run('state.scoreDirty'),true);
run("editToken('delete')");assert.deepEqual(plain(run('state.scoreTokens')),['return',';']);
const payload = (source,value) => ({source,code_source:source,code_tokens:['return',String(value),';'],code_notes:[],notes:[],result:{trace:[{id:0,line:1,col:1,kind:'return',variables:{},stack:[],data:{value}}],output:[],return_value:value,instructions:1}});
context.payloadA=payload('return 1;',1);context.payloadB=payload('return 2;',2);
run("state.source='return 1;';state.comparison={left:payloadA,right:payloadB,comparison:{first_divergence:0}};state.sideBreakpoints={left:new Set([1]),right:new Set()};state.side='left';state.cursor=0;activateRun(payloadA);switchSide('right')");
assert.equal(run('state.run.result.return_value'),2);
assert.equal(run('state.source'),'return 1;', 'switching audition must preserve editable A');
assert.equal(run('state.breakpoints.size'),0,'B must not inherit A breakpoints');
assert.equal(element('source').value,'return 2;');assert.equal(element('source').readOnly,true);
run("switchSide('left')");assert.equal(element('source').readOnly,false);
// Changing a fixture invalidates a pending request and its old score.
run('state.busy=true;state.request=3');element('fixtures').events.input();
assert.equal(run('state.request'),4);assert.equal(run('state.run'),null);assert.equal(run('state.busy'),false);
console.log('Browser v1 state checks passed.');

(async () => {
  // A late response must never resurrect a trace after any fixture edit.
  const requests=[];
  context.fetch=(url,options)=>new Promise(resolve=>requests.push({url,body:JSON.parse(options.body),resolve}));
  run("state.source='return 1;';state.view='runtime'");
  element('fixtures').value='[9007199254740993]';
  const pending=run('runSource()');
  assert.equal(requests[0].body.inputs_json,'[9007199254740993]');
  element('fixtures').value='[2]';element('fixtures').events.input();
  requests[0].resolve({ok:true,json:async()=>context.payloadA});
  await pending;
  assert.equal(run('state.run'),null);
  // Failed musical edits retain the accepted source and keep stale exports disabled.
  run("activateRun(payloadA);state.source='return 1;';state.view='code';state.scoreTokens=['return',';'];state.scoreDirty=true");
  const invalid=run('applyScore()');
  requests[1].resolve({ok:false,json:async()=>({error:'Expected expression at line 1'})});
  await invalid;
  assert.equal(run('state.source'),'return 1;');
  assert.equal(run('state.scoreDirty'),true);
  assert.equal(element('export-code').disabled,true);
  const valid=run("state.scoreTokens=['return','2',';'];applyScore()");
  requests[2].resolve({ok:true,json:async()=>context.payloadB});
  await valid;
  assert.equal(run('state.source'),'return 2;');
  assert.equal(run('state.scoreDirty'),false);
  // Audition schedules only onsets inside the loop, including the start but not the end.
  context.heard=[];
  run("soundNote=(note)=>heard.push(note.start);state.audio={currentTime:0,resume:()=>Promise.resolve()};state.notes=[0,1,2,3].map(start=>({start,duration:.1,pitch:60,velocity:80,channel:0}));state.total=4;state.cursor=0;state.view='runtime';state.run=payloadA");
  element('loop-start').value='1';element('loop-end').value='2';element('loop-enabled').checked=true;
  await run('play()');
  assert.equal(run('state.anchorBeat'),1);
  assert.deepEqual(context.heard,[1]);
  run('state.audio.currentTime=.48;animate()');
  assert.deepEqual(context.heard,[1], 'lookahead must not schedule an onset at loop end');
  run('pause(true)');
  // Initial state and rewind follow beat zero even when its events are muted.
  run(`state.view='runtime';state.comparison=null;state.side='left';state.source='let x=5; return x;';
    activateRun({source:state.source,code_source:state.source,code_tokens:[],code_notes:[],
      notes:[{id:0,event_id:8,start:2,duration:.1,pitch:60,velocity:80,channel:0}],
      result:{trace:Array.from({length:9},(_,id)=>({id,line:1,col:1,kind:id===8?'return':'statement',function:'main',variables:{x:id},data:{value:id},stack:[]})),output:[],return_value:8,instructions:9}})`);
  assert.equal(run('state.cursor'),0);
  assert.equal(run('state.selectedEvent'),0,'initial inspector must follow time zero rather than the first audible note');
  run('seekEvent(8)');
  element('replay').events.click();
  assert.equal(run('state.cursor'),0,'rewind returns to time zero even if the opening passage is muted');
  assert.equal(run('state.selectedEvent'),0);
  // A blank click in a filtered passage follows the full trace, not the previous sound.
  run(`state.view='runtime';state.events=Array.from({length:17},(_,id)=>({id,line:1,col:1,kind:'assign',function:'main',variables:{value:id},data:{value:id},stack:[]}));
    state.eventTimeline=state.events.map((event,index)=>({start:index*.25,index}));
    state.notes=[0,16].map(id=>({id,event_id:id,start:id*.25,duration:.1,pitch:60,velocity:80,channel:0}));
    state.eventNotes=new Map(state.notes.map(note=>[note.event_id,[note]]));state.noteIndices=new Map(state.notes.map((note,index)=>[note.event_id,index]));
    state.total=4.25;state.longest=.1;state.zoom=100;state.lowPitch=43;state.highPitch=84;state.selectedEvent=0;state.selectedNote=0;state.cursor=0;state.loop.enabled=false`);
  element('timeline-scroll').scrollLeft=0;
  element('timeline').events.click({clientX:242,clientY:10});
  assert.equal(run('state.cursor'),2);
  assert.equal(run('state.selectedEvent'),8, 'a silent event must still supply the state at the clicked beat');
  assert.equal(run('state.selectedNote'),-1, 'a muted event has no selected audible note');
  assert.match(element('variables').textContent,/8/);
  // Arrow-key stepping is harmless for an accepted program with no runtime events.
  run(`state.run={source:'',result:{trace:[]}};state.events=[];state.notes=[];state.eventTimeline=[];state.eventNotes.clear();state.selectedEvent=-1;state.selectedNote=-1;state.cursor=0;state.view='runtime';state.scoreDirty=false`);
  await assert.doesNotReject(run('step(1)'));
  await assert.doesNotReject(run('step(-1)'));
  assert.equal(run('state.selectedEvent'),-1);
  // Executable-score stepping continues to work when the runtime trace is empty.
  run(`state.view='code';state.notes=[{id:0,start:0,duration:.1,pitch:96,velocity:80,channel:0}];state.cursor=0;state.selectedNote=-1`);
  await run('step(1)');
  assert.equal(run('state.selectedNote'),0);
  console.log('Browser async invalidation, score validation, loop, filtered seeking, and empty-trace checks passed.');
  // Local performances follow the rendered media clock, including tempo changes and tails.
  class Media {
    constructor(url) { this.src=url; this.currentTime=0; this.paused=true; this.events={}; this.playbackRate=1; }
    addEventListener(kind,fn) { this.events[kind]=fn; }
    async play() { this.paused=false; }
    pause() { this.paused=true; }
    removeAttribute() {} load() {}
  }
  context.Audio=Media;
  context.song={source:'print([144,60,100]);\nprint([128,60,0]);', name:'Song.son',
    notes:[{id:0,event_id:7,start:0,duration:2,pitch:60,velocity:100,channel:0,voice:0,line:1},
      {id:1,event_id:9,start:3,duration:1,pitch:64,velocity:90,channel:1,voice:1,line:2}],
    code_notes:[],code_tokens:[],performance:{id:'Song',title:'Song',audio_url:'/api/performances/Song/audio.wav',midi_url:'/api/performances/Song/performance.mid',duration_seconds:4,duration_beats:8},
    result:{trace:[{id:7,start:0,line:1,col:1,kind:'note_on',data:{emission_line:3},variables:{},stack:[]},
      {id:8,start:2,line:2,col:1,kind:'note_off',data:{},variables:{},stack:[]},
      {id:9,start:3,line:2,col:1,kind:'note_on',data:{},variables:{},stack:[]}], output:['Scheduled MIDI'],return_value:3,instructions:12}};
  context.fetch=async()=>({ok:true,json:async()=>context.song});
  await run("loadPerformance('Song')");
  assert.equal(run('state.total'),8,'song length must use WAV duration, including the synthesis tail');
  assert.equal(element('source').readOnly,true);
  assert.equal(element('runtime-view').textContent,'Song performance');
  assert.match(element('source-link').textContent,/scheduled MIDI events/);
  assert.equal(element('code-view').disabled,true);
  assert.equal(element('compare').disabled,true);
  assert.equal(element('palette').disabled,true);
  assert.equal(element('export-code').disabled,true);
  run('seekEvent(1)');
  assert.equal(run('state.cursor'),2,'silent note-offs retain exact performance time');
  assert.equal(run('state.media.currentTime'),1);
  await run('play()');
  run('state.media.currentTime=1.6;animate()');
  assert.equal(run('state.cursor'),3.2);
  assert.equal(run('state.selectedEvent'),2);
  assert.equal(run('state.selectedLine'),2);
  run('pause(true)');
  assert.equal(run('state.media.paused'),true);
  element('replay').events.click();
  assert.equal(run('state.cursor'),0);
  assert.equal(run('state.media.currentTime'),0);
  run('state.speed=1.5');
  await run('play()');
  assert.equal(run('state.media.playbackRate'),1.5);
  run('pause(true);state.breakpoints=new Set([2]);state.cursor=0');
  await run('play()');
  run('state.media.currentTime=1.1;animate()');
  assert.equal(run('state.playing'),false);
  assert.equal(run('state.cursor'),2,'breakpoints seek to the exact scheduled event');
  assert.equal(run('state.media.currentTime'),1);
  // Looping seeks the media clock itself, so it cannot drift away from the piano roll.
  run('state.breakpoints.clear();state.cursor=2');
  element('loop-start').value='2';element('loop-end').value='4';element('loop-enabled').checked=true;
  await run('play()');
  run('state.media.currentTime=2.1;animate()');
  await new Promise(resolve=>setImmediate(resolve));
  assert.equal(run('state.media.currentTime'),1);
  assert.equal(run('state.cursor'),2);
  assert.equal(run('state.playing'),true);
  run('pause(true)');
  // Native ended may arrive before requestAnimationFrame at a full-song loop boundary.
  element('loop-start').value='0';element('loop-end').value='8';element('loop-enabled').checked=true;
  await run('play()');
  run('state.media.currentTime=4;state.media.events.ended()');
  await new Promise(resolve=>setImmediate(resolve));
  assert.equal(run('state.playing'),true,'the media ended event must preserve full-song looping');
  assert.equal(run('state.media.currentTime'),0);
  run('pause(true)');
  const media=run('state.media');
  run("clearRun();state.source='return 1;';activateRun(payloadA)");
  assert.equal(media.paused,true,'changing modes stops the old performance');
  assert.equal(run('state.media'),null);
  assert.equal(element('source').readOnly,false);
  assert.equal(element('code-view').disabled,false);
  assert.equal(element('runtime-view').textContent,'Execution');
  assert.match(element('source-link').textContent,/execution events/);
  // A slow song fetch cannot overwrite a subsequently chosen normal program.
  let answer;
  context.fetch=()=>new Promise(resolve=>{answer=resolve});
  const songPending=run("loadPerformance('Song')");
  run("clearRun();state.source='return 2;';activateRun(payloadB)");
  answer({ok:true,json:async()=>context.song});
  await songPending;
  assert.equal(run('state.run.result.return_value'),2);
  assert.equal(run('state.media'),null);
  // A rejected pending media play must not pause or replace the newly selected score.
  context.fetch=async()=>({ok:true,json:async()=>context.song});
  await run("loadPerformance('Song')");
  let rejectPlay;
  const oldMedia=run('state.media');
  oldMedia.play=()=>new Promise((resolve,reject)=>{rejectPlay=reject});
  const pendingPlay=run('play()');
  run("clearRun();state.source='return 2;';activateRun(payloadB);state.playing=true");
  rejectPlay(new Error('Old media was unloaded'));
  await pendingPlay;
  assert.equal(run('state.playing'),true,'a stale audio error cannot interrupt the new program');
  assert.equal(element('error-banner').textContent,'');
  run('pause(true)');
  // A fulfilled pending play belongs to its original media element only.
  await run("loadPerformance('Song')");
  let finishPlay;
  const pendingMedia=run('state.media');
  pendingMedia.play=()=>new Promise(resolve=>{finishPlay=resolve});
  const superseded=run('play()');
  await run("loadPerformance('Song')");
  const newMedia=run('state.media');
  finishPlay();await superseded;
  assert.equal(pendingMedia.paused,true);
  assert.equal(run('state.media'),newMedia);
  assert.equal(run('state.playing'),false);
  console.log('Browser local performance media clock, seeking, breakpoints, restore, and stale request checks passed.');

})().catch(error=>{console.error(error);process.exitCode=1;});
