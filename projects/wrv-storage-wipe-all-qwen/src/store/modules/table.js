export const useTableStore = defineStore(
	'useTable',
	() => {
		const tableStoreColumns = reactive({})
		const updateColumns = ({ prop, value }) => {
			tableStoreColumns[prop] = value
		}
		return { tableStoreColumns, updateColumns }
	},
	{ persist: true }
)
