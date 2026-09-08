<script lang="ts">
	import CartaoConjunto from '$lib/CartaoConjunto.svelte';
	import { descreverOrigem, podeEnviar as permiteEnviar } from '$lib/apresentacao';
	import { lerEventos } from '$lib/sse';
	import type { Conjunto, EventoFim, Origem } from '$lib/tipos';

	let pergunta = $state('');
	let resposta = $state('');
	let conjuntos = $state<Conjunto[]>([]);
	let origem = $state<Origem | null>(null);
	let buscando = $state(false);
	let erro = $state('');
	let interrompida = $state(false);

	const podeEnviar = $derived(permiteEnviar(pergunta, buscando));

	async function perguntar(evento: SubmitEvent) {
		evento.preventDefault();
		// Pergunta vazia não dispara requisição, e o envio duplicado é bloqueado
		// enquanto a anterior não termina.
		if (!permiteEnviar(pergunta, buscando)) return;
		const texto = pergunta.trim();

		buscando = true;
		resposta = '';
		conjuntos = [];
		origem = null;
		erro = '';
		interrompida = false;

		let terminou = false;
		try {
			const r = await fetch('/api/perguntar', {
				method: 'POST',
				headers: { 'content-type': 'application/json' },
				body: JSON.stringify({ pergunta: texto })
			});
			if (!r.ok || !r.body) throw new Error('sem corpo');

			for await (const ev of lerEventos(r.body)) {
				if (ev.nome === 'fragmento') {
					resposta += (ev.dados as { texto: string }).texto;
				} else if (ev.nome === 'fim') {
					const fim = ev.dados as EventoFim;
					origem = fim.origem;
					conjuntos = fim.fichas ?? [];
					terminou = true;
				} else if (ev.nome === 'erro') {
					erro = (ev.dados as { mensagem: string }).mensagem;
					terminou = true;
				}
			}
		} catch {
			erro = 'A conexão falhou. Tente perguntar de novo.';
			terminou = true;
		} finally {
			// Sem o evento final a resposta está incompleta. Apresentá-la como
			// pronta faria o usuário confiar num texto cortado no meio.
			if (!terminou && !erro) interrompida = true;
			buscando = false;
		}
	}
</script>

<svelte:head>
	<title>Caminho das Pedras — onde achar dados públicos</title>
	<meta
		name="description"
		content="Pergunte em linguagem comum onde encontrar dados públicos brasileiros."
	/>
</svelte:head>

<main class="mx-auto w-full max-w-2xl px-4 py-8 sm:py-12">
	<header>
		<h1 class="text-2xl font-bold text-slate-900 sm:text-3xl dark:text-slate-100">
			Caminho das Pedras
		</h1>
		<p class="mt-2 text-slate-600 dark:text-slate-400">
			Pergunte com suas palavras onde encontrar um dado público. A resposta traz os
			conjuntos e os links para você conferir.
		</p>
	</header>

	<form class="mt-6" onsubmit={perguntar}>
		<label class="block text-sm font-medium text-slate-700 dark:text-slate-300" for="pergunta">
			Sua pergunta
		</label>
		<div class="mt-2 flex flex-col gap-2 sm:flex-row">
			<input
				id="pergunta"
				name="pergunta"
				type="text"
				autocomplete="off"
				bind:value={pergunta}
				placeholder="quantos casos de dengue na minha cidade"
				class="w-full min-w-0 rounded-md border border-slate-300 bg-white px-3 py-2 text-slate-900 placeholder-slate-400 focus:border-sky-600 focus:ring-2 focus:ring-sky-600 focus:outline-none dark:border-slate-600 dark:bg-slate-900 dark:text-slate-100"
			/>
			<button
				type="submit"
				disabled={!podeEnviar}
				class="rounded-md bg-sky-700 px-4 py-2 font-medium text-white hover:bg-sky-800 focus:ring-2 focus:ring-sky-600 focus:ring-offset-2 focus:outline-none disabled:cursor-not-allowed disabled:bg-slate-400 dark:focus:ring-offset-slate-950"
			>
				{buscando ? 'Buscando…' : 'Perguntar'}
			</button>
		</div>
	</form>

	<div aria-live="polite" class="mt-8">
		{#if buscando && !resposta}
			<p class="text-slate-600 dark:text-slate-400">Procurando no catálogo…</p>
		{/if}

		{#if erro}
			<p
				class="rounded-md border border-amber-300 bg-amber-50 p-3 text-amber-900 dark:border-amber-700 dark:bg-amber-950 dark:text-amber-200"
			>
				{erro}
			</p>
		{/if}

		{#if interrompida}
			<p
				class="rounded-md border border-amber-300 bg-amber-50 p-3 text-amber-900 dark:border-amber-700 dark:bg-amber-950 dark:text-amber-200"
			>
				A resposta foi interrompida antes de terminar, então pode estar incompleta.
				Pergunte de novo para ver a resposta inteira.
			</p>
		{/if}

		{#if resposta}
			<div
				class="rounded-lg border border-slate-200 bg-white p-4 whitespace-pre-wrap text-slate-800 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-200"
			>
				{resposta}
			</div>
		{/if}

		{#if origem && !interrompida}
			<p class="mt-2 text-xs text-slate-500 dark:text-slate-400">
				{descreverOrigem(origem)}
			</p>
		{/if}
	</div>

	{#if conjuntos.length}
		<section class="mt-8">
			<h2 class="text-lg font-semibold text-slate-900 dark:text-slate-100">Confira</h2>
			<p class="mt-1 text-sm text-slate-600 dark:text-slate-400">
				Os conjuntos que a busca encontrou. Abra e confirme antes de usar.
			</p>
			<div class="mt-4 space-y-4">
				{#each conjuntos as conjunto (conjunto.nome)}
					<CartaoConjunto {conjunto} />
				{/each}
			</div>
		</section>
	{/if}
</main>
