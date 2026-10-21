"""Human-authored synthetic gold labels. Never infer or revise them from outputs."""
import base64
import io
import zipfile
from xml.sax.saxutils import escape

from organization_acceptance import docx, pdf

PNG = base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+a7WQAAAAASUVORK5CYII=')
GOAL = '准备课程结题材料包，比较版本和通知冲突，保留缺项，文件操作前确认。'


def xlsx(rows):
    """Real OOXML cached values; no formula evaluation or Office dependency."""
    buffer = io.BytesIO()
    cells = []
    for r, row in enumerate(rows, 1):
        values = []
        for c, value in enumerate(row):
            ref = f'{chr(65+c)}{r}'
            values.append(f'<c r="{ref}"><v>{value}</v></c>' if type(value) in (int, float) else f'<c r="{ref}" t="inlineStr"><is><t>{escape(value)}</t></is></c>')
        cells.append(f'<row r="{r}">{"".join(values)}</row>')
    files = {
        '[Content_Types].xml': '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/><Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/></Types>',
        '_rels/.rels': '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>',
        'xl/workbook.xml': '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="Data" sheetId="1" r:id="rId1"/></sheets></workbook>',
        'xl/_rels/workbook.xml.rels': '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/></Relationships>',
        'xl/worksheets/sheet1.xml': '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData>' + ''.join(cells) + '</sheetData></worksheet>',
    }
    with zipfile.ZipFile(buffer, 'w') as archive:
        for name, content in files.items():
            archive.writestr(zipfile.ZipInfo(name, (2026, 1, 1, 0, 0, 0)), content.encode('utf-8'))
    return buffer.getvalue()


def package_rows():
    rows = []
    def add(path, data, purpose, materials=(), version=None, handling='candidate', readable='expected_success'):
        rows.append(dict(path=path, data=data.encode('utf-8') if isinstance(data, str) else data,
                         purpose=purpose, material_membership=list(materials), submission_required=bool(materials),
                         expected_version=version, expected_handling=handling, expected_read=readable))
    req = '必须提交结题报告、实验记录、费用清单、签字页、验收意见。\n'
    add('通知_原版.txt', req+'报名截止：2026-11-01\n这是人工合成的课程结题通知。', '课程提交要求和截止时间', handling='notice_only')
    add('通知_补充.txt', req+'报名截止：2026-11-03\n这份补充通知与原通知的日期冲突，不能擅自选择。', '相互矛盾的截止时间', handling='notice_conflict')
    base = '本课程研究传感器测量误差，使用重复采样和校准流程验证数据。实验记录原始读数、环境条件、仪器设置和误差来源。结题报告说明研究目标、实验方法、观察结果、局限性和后续改进；本记录不是实际个人材料。' * 3
    for version in (1, 2):
        relation = dict(group='report', revision=version, human_candidate='v2', basis='同材料正文及显式版本，需实测严格阈值')
        add(f'结题报告_v{version}.txt', base+f'\n报告修订版本{version}：补充校准说明。', '课程研究结题报告', ['结题报告'], relation)
        relation = dict(group='experiment', revision=version, human_candidate='v2', basis='同材料正文及显式版本，需实测严格阈值')
        add(f'实验记录_v{version}.docx', docx(base+f' 实验修订版本{version}：第{version}轮校准。'), '课程原始实验记录', ['实验记录'], relation)
    add('费用清单.xlsx', xlsx([['用途', '金额'], ['传感器采购', 400], ['耗材', 50], ['合计', 450]]), '课程实际费用列表', ['费用清单'])
    add('费用凭证.pdf', pdf('Synthetic course expense receipt: sensor 400 and supplies 50. Total 450.'), '费用补充凭证，不替代费用清单', handling='supporting_only')
    add('课程说明.docx', docx('这是一份课程研究背景说明，解释传感器误差，不是签字页或验收意见。'), '研究背景', handling='not_required')
    add('项目总结.txt', base+'\n这是内部交流摘要，未声明为结题报告。', '内部总结', handling='not_required')
    add('附件索引.txt', '附件列表只是引用：签字页尚未签署，验收意见尚未收到；引用不等于文件存在。', '附件引用', handling='needs_confirmation')
    add('预算草稿.xlsx', xlsx([['计划项目', '预算'], ['传感器', 600]]), '未实施的预算草稿', handling='not_required')
    add('course_notes.pdf', pdf('Course notes: sensor calibration and repeated measurement. Not a signed acceptance.'), '教学参考资料', handling='not_required')
    add('personal_schedule.txt', '个人生活安排：周末买菜和清洁，不属于课程提交要求。', '无关个人计划', handling='not_required')
    add('合影.png', PNG, '无正文证据的合成像素，不声称包含人物', handling='needs_confirmation', readable='unsupported_no_ocr')
    add('图像通知.png', PNG, '仅测试无OCR，像素不代表可读取的通知内容', handling='needs_confirmation', readable='unsupported_no_ocr')
    add('损坏记录.pdf', b'deliberately invalid PDF: synthetic parser failure', '故意损坏输入', handling='needs_confirmation', readable='expected_failure')
    add('损坏表格.docx', b'deliberately invalid OOXML', '故意损坏输入', handling='needs_confirmation', readable='expected_failure')
    add('空材料.txt', b'', '明确的空文件异常用例，不用于正文分析', handling='needs_confirmation', readable='expected_failure')
    add('未知数据.bin', b'\x00\xff\x11binary-test', '不支持的二进制', handling='needs_confirmation', readable='unsupported')
    add('参考资料.txt', base+'\n仅作研究参考，不应自动选入提交包。', '参考资料', handling='not_required')
    add('签字页_待确认.txt', '这只是签字页待办说明。尚未取得签署记录，不能把本文件当作已签署材料。', '未签署的待办说明', ['签字页'], handling='needs_confirmation')
    assert len(rows) == 22
    return rows


def classification_rows():
    rows = []
    def add(path, data, label, evidence, allowed=('purpose_from_content', 'file_type_only'), abstain=False):
        extension = path.rsplit('.', 1)[-1]
        rows.append(dict(path=path, data=data.encode('utf-8') if isinstance(data, str) else data,
                         human_category=label, evidence=evidence, allowed_methods=list(allowed),
                         must_abstain_purpose=abstain, human_file_type=extension))
    add('财务/报销说明.txt', '财务报销：办公室耗材费用100元，申请企业费用 reimbursement。', 'finance', '正文明确报销用途')
    add('finance/receipt.docx', docx('企业办公费用报销凭证：耗材100元。'), 'finance', 'DOCX正文同一报销用途')
    add('finance/claim.pdf', pdf('Business expense reimbursement. Office supplies cost 100. Receipt for finance.'), 'finance', 'PDF文本层同一报销用途')
    add('home/notes.txt', '住宅水管维护：厨房漏水，周六请维修人员更换密封圈。', 'home_maintenance', '正文维修用途，不是扩展名')
    add('travel/notes.txt', '旅行行程：乘火车前往杭州，办理住宿并参观博物馆。', 'travel', '同名同扩展名、不同正文用途')
    add('housing/lease.txt', '住房租赁合同草稿：月租2000元，租期一年，尚未签署。', 'housing', '正文住房租赁，不代表法律有效')
    add('misleading/holiday_plan.txt', '这是企业交通费用报销单，金额80元，与度假计划无关。', 'finance', '文件名误导，必须以正文为依据', ('purpose_from_content',))
    add('misleading/invoice.txt', '住房租赁续租约定：月租1800元，续租六个月，不是发票。', 'housing', '文件名与正文不一致', ('purpose_from_content',))
    add('中文/清单.txt', '家庭采购清单：牛奶、蔬菜、纸巾，下班后去超市。', 'household', '正文家庭采购')
    add('health/appointment.txt', '合成日程：预约常规健康检查，仅记录预约事项，无真实姓名或病史。', 'health_schedule', '日程用途，不推断诊断')
    add('work/meeting.txt', '公司行政会议：讨论办公室轮值和公共设备预约，不是课程或比赛。', 'work_admin', '行政办公正文')
    add('personal/diary.txt', '个人日记：周末散步，阅读小说，与家人做饭。', 'personal', '生活记录正文')
    add('table/expenses.xlsx', xlsx([['Business reimbursement', 'Amount'], ['Office supplies', 100]]), 'finance', '工作表缓存值，不计算公式')
    for path, data, evidence in [
        ('unknown/empty.txt', b'', '没有正文'), ('unknown/blank.txt', b'  \n\t', '仅空白'),
        ('broken/record.pdf', b'invalid PDF', '故意损坏，不具备可提取证据'),
        ('broken/record.docx', b'invalid OOXML', '故意损坏，不具备可提取证据'),
        ('image/receipt.png', PNG, '无OCR，不因文件名发票而判定财务'),
        ('binary/data.bin', b'\x00\xff\x11', '不支持的二进制'),
        ('ambiguous/计划.txt', '明天处理，具体事项和用途待定。', '正文不足以判断用途'),
    ]:
        add(path, data, None, evidence, ('file_type_only', 'abstain'), True)
    assert len(rows) == 20
    return rows
