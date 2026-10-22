const test = require('node:test');
const assert = require('node:assert/strict');
const CourseWorkflow = require('../course-workflow.js');

test('target count is a reference, not a hard file limit', () => {
  assert.equal(CourseWorkflow.TARGET_COUNT, 22);
  const files = Array.from({length:24}, (_,i) => ({id:String(i),category:'待确认',isReportCandidate:false}));
  assert.equal(CourseWorkflow.getProgress(files,null).imported,24);
});

test('unknown categories stay pending rather than being inferred', () => {
  const model = CourseWorkflow.buildDirectoryModel([
    {id:'a',category:'待确认'},
    {id:'b',category:'not-a-supported-category'}
  ]);
  assert.equal(model.length,1);
  assert.equal(model[0].category,'待确认');
  assert.equal(model[0].files.length,2);
});

test('directory model groups only the category explicitly supplied by the user', () => {
  const model = CourseWorkflow.buildDirectoryModel([
    {id:'a',category:'课程资料'},
    {id:'b',category:'课程资料'},
    {id:'c',category:'报告与总结'}
  ]);
  assert.deepEqual(model.map(group => [group.category,group.files.length]), [
    ['课程资料',2],['报告与总结',1]
  ]);
});

test('report version remains unselected until a marked candidate is explicitly chosen', () => {
  const files = [
    {id:'a',category:'报告与总结',isReportCandidate:true},
    {id:'b',category:'报告与总结',isReportCandidate:false}
  ];
  assert.equal(CourseWorkflow.getProgress(files,null).selectedReport,null);
  assert.equal(CourseWorkflow.getProgress(files,'b').selectedReport,null);
  assert.equal(CourseWorkflow.getProgress(files,'a').selectedReport,'a');
});

test('file metadata helpers handle extensions, hidden files, sizes and HTML escaping', () => {
  assert.equal(CourseWorkflow.getExtension('实验报告.PDF'),'pdf');
  assert.equal(CourseWorkflow.getExtension('.gitignore'),'file');
  assert.equal(CourseWorkflow.formatBytes(0),'0 B');
  assert.equal(CourseWorkflow.formatBytes(1024),'1.0 KB');
  assert.equal(CourseWorkflow.escapeHtml('<script>"x"&</script>'),'&lt;script&gt;&quot;x&quot;&amp;&lt;/script&gt;');
});