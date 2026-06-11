<template>
	<div class="flex-start">
		<t-rate :value="value" disabled></t-rate>
		<span>{{ text }}</span>
	</div>
</template>

<script>
export default {
	props: {
		strength: {
			type: Number,
			default: 0,
			validator(value) {
				return value >= 0 && value <= 5
			}
		}
	},
	data() {
		return {
			value: 0
		}
	},
	watch: {
		strength(value) {
			this.value = value
		}
	},

	computed: {
		text() {
			return this.strength == 0 ? '不符合' : ['弱', '弱', '中', '中', '强', '强'][this.strength]
		}
	}
}
</script>
