/* Synthetic local UI fixtures. NOT scanned files, backend payloads, or taxonomy. */
(function (root) {
    const base=()=>({localPreview:true,pathStyle:'windows',outputRoot:'E:\\UI演示输出（未创建）',categories:[],folders:[],pending:[],excluded:[]});
    const file=(filename,source,target,evidenceKind,reason)=>({filename,source,target,evidenceKind,reason});
    function get(name) {
        const data=base();
        if(name==='empty')return data;
        if(name==='incomplete')return {localPreview:true,categories:[]};
        if(name==='unknown') {data.pending=[{filename:'未命名文件.pdf',source:'E:\\虚构输入\\未命名文件.pdf',reason:'仅凭演示文件名和扩展名无法确定用途，未提供可读取文本。'}];return data;}
        if(name==='single') {data.categories=[{name:'文本文件',files:[file('备忘.txt','C:\\虚构输入\\备忘.txt',['文本文件','备忘.txt'],'file_type','.txt 扩展名；未判断文件用途。')]}];return data;}
        if(!['mixed','collision'].includes(name))return null;
        data.categories=[
            {name:'阅读笔记',files:[file('摘录.docx','C:\\本地UI样本\\摘录.docx',['阅读','笔记','摘录.docx'],'text','虚构文本片段：“阅读摘录”。仅用于展示依据样式。')]},
            {name:'图片文件',files:[file('photo1.jpg','E:\\本地UI样本\\photo1.jpg',['图片','photo1.jpg'],'file_type','.jpg 扩展名；未判断图片内容。'),file('photo2.png','E:\\本地UI样本\\photo2.png',['图片','photo2.png'],'file_type','.png 扩展名；未判断图片内容。')]}
        ];
        data.folders=[['留空的目录']];
        data.pending=[{filename:'附件.pdf',source:'E:\\本地UI样本\\附件.pdf',reason:'没有足够证据说明用途，保留待人工确认。'}];
        data.excluded=[{filename:'应用缓存.bin',source:'E:\\本地UI样本\\应用缓存.bin',reason:'本地场景明确列为不参与整理；未读取文件。'}];
        if(name==='collision')data.categories[1].files.push(file('PHOTO1.JPG','D:\\另一虚构目录\\PHOTO1.JPG',['图片','PHOTO1.JPG'],'file_type','仅依据扩展名；与已有建议目标可能同名。'));
        return data;
    }
    const api={get};if(typeof module!=='undefined'&&module.exports)module.exports=api;else root.OrganizationDemo=api;
})(typeof window==='undefined'?globalThis:window);
