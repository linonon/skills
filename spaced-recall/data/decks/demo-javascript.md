# JavaScript 基礎

tags: javascript, frontend, basics

---

Q: `===` 和 `==` 的差別是什麼？
A: `===` 是嚴格相等，比較值和類型；`==` 是寬鬆相等，會做類型轉換。

---

Q: `let`、`const`、`var` 三者的差別？
A: `var` 是函數作用域，有提升（hoisting）；`let` 是區塊作用域，不可重複宣告；`const` 是區塊作用域，不可重新賦值。

---

Q: 什麼是 closure（閉包）？
A: 閉包是一個函數能記住並存取它被定義時的詞法作用域（lexical scope），即使在該作用域外執行。

---

Q: `Promise` 的三種狀態是什麼？
A: pending（進行中）、fulfilled（已完成）、rejected（已拒絕）。一旦從 pending 變為 fulfilled 或 rejected，就不可逆。

---

Q: `null` 和 `undefined` 的差別？
A: `undefined` 是變數已宣告但未賦值的預設值；`null` 是刻意賦予的「空值」，表示「沒有值」。
