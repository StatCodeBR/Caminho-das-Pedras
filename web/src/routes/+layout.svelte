<script lang="ts">
	import './layout.css';

	let { children } = $props();
</script>

<svelte:head>
	<!-- Servidos de `static/`, não importados de `$lib`: o navegador pede o
	     favicon antes de qualquer JavaScript, e um caminho fixo evita que ele
	     mude de nome a cada build. -->
	<link rel="icon" href="/favicon.png" sizes="32x32" />
	<link rel="apple-touch-icon" href="/apple-touch-icon.png" />
</svelte:head>
{@render children()}
