<script setup lang="ts">
import { RouterLink } from 'vue-router'
</script>

<template>
  <section class="nf">
    <h1>ページが見つかりません</h1>
    <p>URL をご確認ください。</p>
    <RouterLink to="/" class="nf__link">マイページへ戻る</RouterLink>
  </section>
</template>

<style scoped>
.nf { text-align: center; padding: 80px 0; }
.nf h1 { font-size: 20px; margin: 0 0 8px; }
.nf p { color: var(--muted); margin: 0 0 20px; }
.nf__link {
  color: var(--accent-dark); font-weight: 600; text-decoration: none;
  padding: 8px 16px; border: 1px solid var(--line); border-radius: 8px;
}
.nf__link:hover { background: var(--accent-soft); }
</style>
