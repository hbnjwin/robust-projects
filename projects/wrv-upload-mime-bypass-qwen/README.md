# wrv-upload-mime-bypass

## Question ID: l1-062

## Task Type: bug-fix

## App Domain: web_frontend

## Language: js

## Model: qwen

## Query

专家库文档上传弹窗，允许的文件类型是 PDF/DOCX/XLSX/DOC，但实际有三个问题：1) 把 .exe 文件改后缀名为 .docx 就能上传成功，前端只校验了文件扩展名没有校验 MIME 类型；2) 上传 .xlsx 文件时前端校验通过了但后端 OCR 处理报格式错误，用户收不到任何提示；3) 同一个文件重复上传没有去重检查，文档列表出现完全相同的记录。三个问题帮我一起修了。
