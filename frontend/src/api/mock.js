/**
 * GitHub Pages 静态演示数据层。
 * 仅在 VITE_DEMO_MODE=true 时启用，不依赖 Django 后端。
 */
import rawWords from '../../../core/data/word_bank.json'

const STATE_KEY = 'zhishucixun_pages_state_v1'
const DEMO_TOKEN = 'pages-demo-token'
const DEMO_USER = { id: 1, username: 'demo', nickname: '演示学习者', first_name: '演示学习者' }

export const isDemoMode = import.meta.env.VITE_DEMO_MODE === 'true'

const WORDS = rawWords.map((w, index) => ({
  id: index + 1,
  word: w.word,
  phonetic: w.phonetic || '',
  pos: w.pos || '',
  meaning: w.meaning || '',
  example: w.example || '',
  example_cn: w.example_cn || '',
  synonyms: w.synonyms || [],
  freq_read: Number(w.freq_read || 0),
  freq_listen: Number(w.freq_listen || 0),
  freq_translate: Number(w.freq_translate || 0),
  freq_write: Number(w.freq_write || 0),
  freq_total: Number(w.freq_read || 0) + Number(w.freq_listen || 0) + Number(w.freq_translate || 0) + Number(w.freq_write || 0),
  difficulty: Number(w.difficulty || 2),
  mnemonic: w.mnemonic || '',
  collocations: w.collocations || [],
  confusables: w.confusables || []
}))

function seedState() {
  const now = Date.now()
  const states = {}
  WORDS.slice(0, 10).forEach((w, index) => {
    const wrong = index % 4 === 0 ? 2 : index % 3
    const correct = 2 + (index % 4)
    const stubborn = wrong >= 2 && index % 3 === 0
    states[w.id] = {
      stage: stubborn ? 2 : 1 + (index % 4),
      ease: stubborn ? 2.05 : 2.5 + (index % 3) * 0.05,
      lapses: stubborn ? 3 : index % 2,
      wrong_count: stubborn ? 3 : wrong,
      correct_count: correct,
      is_new: false,
      next_review_at: index < 4 ? new Date(now - (index + 1) * 3600000).toISOString() : new Date(now + (index - 3) * 86400000).toISOString(),
      interval_minutes: 10 * Math.pow(1.55, index + 1)
    }
  })
  return { states, records: [] }
}

function readState() {
  try {
    const value = JSON.parse(localStorage.getItem(STATE_KEY))
    if (value && value.states) return value
  } catch (e) { /* ignore */ }
  const seeded = seedState()
  writeState(seeded)
  return seeded
}

function writeState(state) {
  localStorage.setItem(STATE_KEY, JSON.stringify(state))
}

function retention(state) {
  const total = Number(state.correct_count || 0) + Number(state.wrong_count || 0)
  return total ? Math.round((Number(state.correct_count || 0) / total) * 100) / 100 : 0
}

function reasons(word, state) {
  const wrong = Number((state && state.wrong_count) || 0)
  const topic = Number(word.freq_read || 0)
  return {
    priority: Math.round((word.freq_total || 1) * (word.difficulty || 1) * (1 + wrong * 0.5) * 100) / 100,
    freq_total: word.freq_total || 0,
    topic_freq: topic,
    difficulty: word.difficulty || 1,
    forgetting: wrong ? Math.round((1 + wrong * 0.5) * 100) / 100 : 1
  }
}

function wordView(word, state, isNew) {
  return Object.assign({}, word, {
    is_new: isNew === undefined ? !state : !!isNew,
    stage: state ? state.stage : 0,
    ease: state ? state.ease : 2.5,
    lapses: state ? state.lapses : 0,
    wrong_count: state ? state.wrong_count : 0,
    correct_count: state ? state.correct_count : 0,
    next_review_at: state ? state.next_review_at : null,
    retention: state ? retention(state) : 0
  })
}

function applyQuality(wordId, quality) {
  const state = readState()
  const current = state.states[wordId] || {
    stage: 0, ease: 2.5, lapses: 0, wrong_count: 0, correct_count: 0, is_new: true, next_review_at: null
  }
  const remembered = Number(quality) >= 3
  current.correct_count = Number(current.correct_count || 0) + (remembered ? 1 : 0)
  current.wrong_count = Number(current.wrong_count || 0) + (remembered ? 0 : 1)
  if (remembered) {
    current.stage = Number(current.stage || 0) + 1
    current.ease = Math.min(3.2, Number(current.ease || 2.5) + 0.06)
  } else {
    current.stage = 0
    current.lapses = Number(current.lapses || 0) + 1
    current.ease = Math.max(1.3, Number(current.ease || 2.5) - 0.18)
  }
  const minutes = remembered ? Math.max(10, Math.round(10 * Math.pow(1.55, current.stage) * current.ease / 2.5)) : 10
  current.interval_minutes = minutes
  current.next_review_at = new Date(Date.now() + minutes * 60000).toISOString()
  current.is_new = false
  state.states[wordId] = current
  state.records.push({ word_id: wordId, quality, at: new Date().toISOString() })
  writeState(state)
  return {
    word_id: wordId,
    stage: current.stage,
    interval_minutes: minutes,
    next_review_at: current.next_review_at,
    lapses: current.lapses
  }
}

function stats() {
  const state = readState()
  const learned = Object.keys(state.states).length
  const mastered = Object.values(state.states).filter((x) => Number(x.stage || 0) >= 5).length
  const due = Object.values(state.states).filter((x) => x.next_review_at && new Date(x.next_review_at).getTime() <= Date.now()).length
  const wrongRecords = state.records.filter((x) => Number(x.quality) < 3).length
  const correctRecords = state.records.filter((x) => Number(x.quality) >= 3).length
  const stubborn = Object.values(state.states).filter((x) => Number(x.lapses || 0) >= 3 || Number(x.wrong_count || 0) >= 3).length
  const accuracy = state.records.length ? correctRecords / state.records.length : 0.78
  const daily = []
  for (let i = 6; i >= 0; i--) {
    const d = new Date(Date.now() - i * 86400000)
    daily.push({ date: d.toISOString().slice(0, 10), count: i === 0 ? Math.min(28, state.records.length + 8) : 4 + ((i * 3) % 11) })
  }
  return {
    learned_total: learned,
    mastered,
    due_today: due,
    new_remaining: Math.max(0, WORDS.length - learned),
    streak_days: Math.max(1, Math.min(7, learned ? 3 : 0)),
    accuracy,
    wrong_count: wrongRecords,
    stubborn_count: stubborn,
    topics: [
      { topic: 'read', total: 24, correct: 20, accuracy: 0.83 },
      { topic: 'listen', total: 12, correct: 8, accuracy: 0.67 },
      { topic: 'translate', total: 10, correct: 7, accuracy: 0.7 },
      { topic: 'write', total: 8, correct: 6, accuracy: 0.75 }
    ],
    plan_done: state.records.length,
    plan_total: Math.max(12, state.records.length + 8),
    daily
  }
}

function plan() {
  const state = readState()
  const learnedIds = new Set(Object.keys(state.states).map(Number))
  const newItems = WORDS.filter((w) => !learnedIds.has(w.id)).slice(0, 8).map((w) => ({
    kind: 'learn', word: wordView(w, null, true), reasons: reasons(w, null)
  }))
  const review = []
  const stubborn = []
  WORDS.forEach((w) => {
    const st = state.states[w.id]
    if (!st) return
    const item = { kind: 'review', word: wordView(w, st, false), reasons: reasons(w, st) }
    if (Number(st.lapses || 0) >= 3 || Number(st.wrong_count || 0) >= 3) {
      item.kind = 'stubborn'
      stubborn.push(item)
    } else if (st.next_review_at && new Date(st.next_review_at).getTime() <= Date.now()) {
      review.push(item)
    }
  })
  const forecast = []
  for (let i = 1; i <= 7; i++) forecast.push({ date: new Date(Date.now() + i * 86400000).toISOString().slice(0, 10), total: (i * 2 + 3) % 9 })
  const queued = newItems.length + review.length + stubborn.length
  return {
    date: new Date().toISOString().slice(0, 10),
    completed: state.records.length,
    total: Math.max(queued, state.records.length),
    progress: 0.42,
    learn_new: newItems,
    review,
    stubborn,
    forecast
  }
}

function notebook(kind) {
  const state = readState()
  const items = []
  WORDS.forEach((w) => {
    const st = state.states[w.id]
    if (!st) return
    const isStubborn = Number(st.lapses || 0) >= 3 || Number(st.wrong_count || 0) >= 3
    if (kind === 'stubborn' && !isStubborn) return
    if (kind === 'wrong' && Number(st.wrong_count || 0) <= 0) return
    items.push({
      word: wordView(w, st, false),
      wrong_count: st.wrong_count || 0,
      lapses: st.lapses || 0,
      last_wrong_at: new Date(Date.now() - (w.id + 1) * 7200000).toISOString()
    })
  })
  return items
}

function trainQuestions(options) {
  const pool = options && options.word ? WORDS.filter((w) => w.word.toLowerCase() === String(options.word).toLowerCase()) : WORDS
  const base = (pool.length ? pool : WORDS).slice(0, options && options.count ? options.count : 4)
  return base.map((w, i) => {
    const others = WORDS.filter((x) => x.id !== w.id).slice(i, i + 3).map((x) => x.meaning)
    return {
      type: 'choice',
      topic: (options && options.topic) || 'read',
      stem: w.word,
      hint: w.phonetic + ' ' + w.pos,
      options: [w.meaning].concat(others),
      answer: w.meaning,
      explanation: w.pos + ' ' + w.meaning + '；例：' + w.example,
      word_id: w.id,
      word: w.word,
      difficulty: w.difficulty,
      listen: (options && options.topic) === 'listen'
    }
  })
}

function planner() {
  const s = stats()
  return {
    summary: '共学习 ' + s.learned_total + ' 词，掌握 ' + s.mastered + ' 词，正确率 ' + Math.round(s.accuracy * 100) + '%，连续学习 ' + s.streak_days + ' 天。',
    strengths: ['阅读词汇基础较好', '复习记录保持稳定'],
    weaknesses: ['听力辨音需要加强', '顽固词仍需专项训练'],
    advice: [
      '今日优先完成到期复习，再用 8～10 个新词扩充词汇量。',
      '针对听力题型进行辨音训练，并复盘形近词。',
      '将顽固词加入专项特训，训练结果会自动回流到学习计划。'
    ],
    stats: s,
    note: 'GitHub Pages 静态演示：使用浏览器本地数据和本地规则引擎。'
  }
}

function tutor(wordName) {
  const w = WORDS.find((x) => x.word.toLowerCase() === String(wordName || '').toLowerCase()) || WORDS[0]
  return {
    word: w.word,
    meaning: w.meaning,
    phonetic: w.phonetic,
    pos: w.pos,
    explanation: w.pos + ' ' + w.meaning,
    mnemonic: w.mnemonic,
    collocations: w.collocations,
    confusable: w.confusables,
    usage: w.example,
    example_cn: w.example_cn,
    note: '本地词汇辅导（GitHub Pages 演示模式）'
  }
}

function analyze(wordName) {
  const w = WORDS.find((x) => x.word.toLowerCase() === String(wordName || '').toLowerCase()) || WORDS[0]
  return {
    word: w.word,
    analysis: '该词存在词义辨析与拼写混淆风险，建议结合搭配和例句进行主动回忆。',
    suggestion: '先朗读例句，再用遮盖释义的方式连续回忆 3 次，并在 24 小时后复习。',
    note: '本地错题归因（GitHub Pages 演示模式）'
  }
}

function delay(value, ms) {
  return new Promise((resolve) => setTimeout(() => resolve(value), ms || 90))
}

export function ensureDemoSession() {
  if (!isDemoMode) return
  if (!localStorage.getItem('ct4_token')) localStorage.setItem('ct4_token', JSON.stringify(DEMO_TOKEN))
  if (!localStorage.getItem('ct4_user')) localStorage.setItem('ct4_user', JSON.stringify(DEMO_USER))
  readState()
}

export async function mockRequest(method, url, data) {
  const [path, queryString = ''] = String(url).split('?')
  const query = new URLSearchParams(queryString)
  const body = data || {}

  if (path === '/api/health') return delay({ status: 'ok', mode: 'github-pages' })
  if (path === '/api/auth/login') return delay({ access_token: DEMO_TOKEN, user: { id: 1, username: body.username || 'demo', nickname: body.username || '演示学习者' } })
  if (path === '/api/auth/register') return delay({ access_token: DEMO_TOKEN, user: { id: 1, username: body.username || 'demo', nickname: body.nickname || body.username || '演示学习者' } })
  if (path === '/api/auth/me') return delay({ id: 1, username: 'demo', nickname: '演示学习者' })

  if (path === '/api/words/today') {
    const limit = Number(query.get('limit') || 40)
    const state = readState()
    const list = WORDS.slice(0, limit).map((w) => wordView(w, state.states[w.id], !state.states[w.id]))
    return delay({ items: list })
  }

  if (path === '/api/words/lookup') {
    const name = String(query.get('word') || '').toLowerCase()
    const w = WORDS.find((x) => x.word.toLowerCase() === name)
    if (!w) throw new Error('词库中未找到该单词')
    const state = readState()
    return delay(wordView(w, state.states[w.id], !state.states[w.id]))
  }

  if (/^\/api\/words\/\d+$/.test(path)) {
    const id = Number(path.split('/').pop())
    const w = WORDS.find((x) => x.id === id)
    if (!w) throw new Error('单词不存在')
    const state = readState()
    return delay(wordView(w, state.states[w.id], !state.states[w.id]))
  }

  if (path === '/api/words') {
    const q = String(query.get('q') || '').toLowerCase()
    const topic = query.get('topic') || ''
    const sort = query.get('sort') || 'word'
    const page = Number(query.get('page') || 1)
    const size = Number(query.get('size') || 30)
    let list = WORDS.filter((w) => !q || w.word.toLowerCase().includes(q) || w.meaning.includes(q))
    if (topic) list = list.filter((w) => Number(w['freq_' + topic] || 0) > 0)
    if (sort === 'freq') list = list.slice().sort((a, b) => b.freq_total - a.freq_total)
    else if (sort === 'difficulty') list = list.slice().sort((a, b) => b.difficulty - a.difficulty)
    else list = list.slice().sort((a, b) => a.word.localeCompare(b.word))
    const start = (page - 1) * size
    const state = readState()
    return delay({
      total: list.length,
      page,
      size,
      items: list.slice(start, start + size).map((w) => wordView(w, state.states[w.id], !state.states[w.id]))
    })
  }

  if (path === '/api/records') return delay(applyQuality(Number(body.word_id || 1), Number(body.quality || 4)))
  if (path === '/api/records/sync') {
    const results = (body.records || []).map((r) => applyQuality(Number(r.word_id || 1), Number(r.quality || 4)))
    return delay({ results })
  }

  if (path === '/api/stats/summary') return delay(stats())
  if (path === '/api/plan/daily') return delay(plan())
  if (path === '/api/notebook/wrong') return delay(notebook('wrong'))
  if (path === '/api/notebook/stubborn') return delay(notebook('stubborn'))
  if (path === '/api/notebook/summary') {
    return delay({ wrong_total: notebook('wrong').length, stubborn_total: notebook('stubborn').length })
  }

  if (path === '/api/ai/example') {
    const w = WORDS.find((x) => x.id === Number(body.word_id)) || WORDS.find((x) => x.word === body.word) || WORDS[0]
    return delay({
      examples: [
        { en: w.example, cn: w.example_cn },
        { en: 'The word "' + w.word + '" appears frequently in CET-4 reading tasks.', cn: '“' + w.word + '”在四级阅读中出现频率较高。' }
      ],
      note: '本地例句库（GitHub Pages 演示模式）'
    })
  }
  if (path === '/api/agents/plan') return delay(planner())
  if (path === '/api/agents/tutor') return delay(tutor(body.word))
  if (path === '/api/agents/train') return delay({ questions: trainQuestions(body), topic: body.topic || 'read', note: '本地出题引擎（GitHub Pages 演示模式）' })
  if (path === '/api/agents/analyze') return delay(analyze(body.word))

  return delay({ detail: '静态演示模式未实现的接口：' + path }, 40)
}