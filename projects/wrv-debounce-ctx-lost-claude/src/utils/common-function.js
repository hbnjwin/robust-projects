export const toImage = (name) => {
	return new URL(`/src/assets/image/${name}`, import.meta.url).href
}
export const findLabel = (value, options, labelKey = 'label', valueKey = 'value') => {
	return options.find((item) => item[valueKey] == value)?.[labelKey] || value
}

export const findLabelOutput = (value, options, labelKey = 'label', valueKey = 'value') => {
	return options.find((item) => item[valueKey] == value)?.[labelKey] || ''
}

export const uuid = () => {
	const temp_url = URL.createObjectURL(new Blob())
	const uuid = temp_url.toString()
	URL.revokeObjectURL(temp_url)
	return uuid.substring(uuid.lastIndexOf('/') + 1)
}

export const fileTypeIcon = (type) => {
	if (!type) return ''
	let extension = type.split('.').pop().toLowerCase()
	let iconList = {
		txt: toImage('data-warehouse/TXT.png'),
		md: toImage('data-warehouse/Markdown.png'),
		pdf: toImage('data-warehouse/PDF.png'),
		html: toImage('data-warehouse/HTML.png'),
		htm: toImage('data-warehouse/HTML.png'),
		xlsx: toImage('data-warehouse/XLSX.png'),
		docx: toImage('data-warehouse/Word.png'),
		csv: toImage('data-warehouse/TXT.png'),
		png: toImage('data-warehouse/img.png'),
		jpg: toImage('data-warehouse/img.png'),
		jpeg: toImage('data-warehouse/img.png'),
		gif: toImage('data-warehouse/img.png'),
		pptx: toImage('data-warehouse/PPT.png'),
		yml: toImage('data-warehouse/YML.png'),
		yaml: toImage('data-warehouse/YML.png')
	}
	return iconList[extension] || iconList.txt
}
export function queryURLParams(url) {
	const params = url.split('?')[1]
	const urlSearchParams = new URLSearchParams(params)
	return Object.fromEntries(urlSearchParams.entries())
}

export const isNullOrUndefined = (value) => {
	return value === undefined || value === null
}
// 16进制字符串转2进制
export const hexToUint8Array = (hexString) => {
	if (hexString.length % 2 !== 0) {
		throw new Error('Invalid hex string')
	}
	const arrayBuffer = new Uint8Array(hexString.length / 2)
	for (let i = 0; i < hexString.length; i += 2) {
		arrayBuffer[i / 2] = parseInt(hexString.substr(i, 2), 16)
	}
	return arrayBuffer
}
// 防抖
export const debounce = (func, wait, immediate = true) => {
	let timeout
	return function () {
		const args = arguments
		if (immediate && !timeout) {
			func.apply(this, args)
		}
		clearTimeout(timeout)
		timeout = setTimeout(() => {
			// 如果没有设置立即执行，在等待时间后执行
			if (immediate) {
				func.apply(this, args)
			}
		}, wait)
	}
}

export const isHttpUrl = (str) => {
	const pattern = /^https?:\/\/(?:www\.)?[-a-zA-Z0-9@:%._\\+~#=]{1,256}\.[a-zA-Z0-9()]{1,6}\b(?:[-a-zA-Z0-9()@:%_\\+.~#?&\\/=]*)$/
	return pattern.test(str)
}
