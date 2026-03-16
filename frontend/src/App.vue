<template>
  <router-view />
</template>

<script setup>
// Vue Router를 사용하여 페이지 관리
</script>

<style>
/* 전역 스타일 리셋 */
* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

#app {
  font-family: 'Noto Sans KR', 'Inter', 'Space Grotesk', system-ui, sans-serif;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
  color: #000000;
  background-color: #ffffff;
}

/* 스크롤바 스타일 */
::-webkit-scrollbar {
  width: 8px;
  height: 8px;
}

::-webkit-scrollbar-track {
  background: #f1f1f1;
}

::-webkit-scrollbar-thumb {
  background: #000000;
}

::-webkit-scrollbar-thumb:hover {
  background: #333333;
}

/* 전역 버튼 스타일 */
button {
  font-family: inherit;
}
</style>
