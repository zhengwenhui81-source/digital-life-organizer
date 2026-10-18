const {test}=require('node:test');
const assert=require('node:assert/strict');
const preview=require('../organization-preview.js');
const demo=require('../organization-demo.js');

test('not started, empty result and incomplete data remain different states',()=>{
    assert.equal(preview.analyze(null).state,'not_started');
    assert.match(preview.render(null),/尚未开始/);
    assert.equal(preview.analyze(demo.get('empty')).files.length,0);
    assert.match(preview.render(demo.get('empty')),/分类结果为空/);
    for(const data of [{},demo.get('incomplete'),{...demo.get('empty'),categories:null}]){
        assert.equal(preview.analyze(data).state,'incomplete');assert.match(preview.render(data),/数据结构不完整/);
        assert.doesNotMatch(preview.render(data),/将复制的文件/);
    }
});
test('single file renders source, explicit destination and type-only evidence',()=>{
    const data=demo.get('single'), model=preview.analyze(data), html=preview.render(data);
    assert.equal(model.files.length,1);assert.match(html,/文本文件 · 1 个文件/);assert.match(html,/按文件类型归类/);
    assert.ok(html.includes('C:\\虚构输入\\备忘.txt'));assert.ok(html.includes('E:\\UI演示输出（未创建）\\文本文件\\备忘.txt'));
    assert.doesNotMatch(html,/\/E:\//);assert.match(html,/未判断文件用途/);
});
test('dynamic categories, nested folders, all files and empty folders survive',()=>{
    const data=demo.get('mixed');data.categories[0].name='任意新分类';
    const before=JSON.stringify(data), model=preview.analyze(data), html=preview.render(data);
    assert.equal(model.files.length,3);assert.match(html,/任意新分类 · 1 个文件/);assert.match(html,/图片文件 · 2 个文件/);
    assert.ok(model.tree.folders.get('阅读').folders.has('笔记'));assert.ok(model.tree.folders.has('留空的目录'));
    assert.match(html,/<details/);assert.match(html,/空文件夹/);assert.equal(JSON.stringify(data),before);
});
test('all uncertain files remain pending without any suggested copy or target folder',()=>{
    const data=demo.get('unknown'), model=preview.analyze(data), html=preview.render(data);
    assert.equal(model.files.length,0);assert.equal(model.folders.length,0);assert.match(html,/待人工确认/);
    assert.match(html,/没有拟复制的文件/);assert.match(html,/不参与自动整理/);
    const mixed=preview.analyze(demo.get('mixed'));
    assert.equal(mixed.files.some(f=>f.filename==='附件.pdf'||f.filename==='应用缓存.bin'),false);
});
test('Windows duplicate target collisions retain every candidate and do not auto-select',()=>{
    const data=demo.get('collision'), model=preview.analyze(data), html=preview.render(data);
    assert.equal(model.conflicts.length,1);assert.equal(model.conflicts[0].length,2);assert.equal(model.files.length,4);
    assert.match(html,/不会覆盖或自动选择/);assert.ok(html.includes('D:\\另一虚构目录\\PHOTO1.JPG'));
    const f=demo.get('single');f.folders.push(f.categories[0].files[0].target);
    assert.equal(preview.analyze(f).conflicts.length,1);
});
test('UNC paths and POSIX presentation preserve their roots',()=>{
    const data=demo.get('single');data.outputRoot='\\\\server\\share\\预览';
    assert.ok(preview.render(data).includes('\\\\server\\share\\预览\\文本文件\\备忘.txt'));
    data.pathStyle='posix';data.outputRoot='/tmp/preview/';assert.equal(preview.destination(data,['a','x.txt']),'/tmp/preview/a/x.txt');
});
test('malicious names, paths, evidence and category labels are escaped everywhere',()=>{
    const data=demo.get('single'), evil='<img src=x onerror="globalThis.pwned=true">&\'';
    data.outputRoot=evil;data.categories[0].name=evil;
    Object.assign(data.categories[0].files[0],{filename:evil,source:evil,target:[evil],reason:evil});
    const html=preview.render(data);assert.doesNotMatch(html,/<img|<script/);assert.ok(html.includes('&lt;img'));
    assert.ok(html.includes('&quot;'));assert.ok(html.includes('&amp;'));assert.ok(html.includes('&#39;'));
});
test('missing fields, unsupported evidence, traversal segments and excessive depth fail closed',()=>{
    for(const mutate of [d=>delete d.pending,d=>d.categories[0].files[0].source=null,d=>d.categories[0].files[0].evidenceKind='guess',d=>d.categories[0].files[0].target=['..','file'],d=>d.folders=[Array(33).fill('a')]]){
        const data=demo.get('single');mutate(data);assert.equal(preview.analyze(data).state,'incomplete');
    }
});
test('all local scenarios render without fetching any API',()=>{
    const original=global.fetch;global.fetch=()=>{throw Error('No API allowed');};
    try{for(const name of ['mixed','single','empty','unknown','collision','incomplete'])assert.equal(typeof preview.render(demo.get(name)),'string');}
    finally{global.fetch=original;}
});
