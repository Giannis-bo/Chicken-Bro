const test = require('node:test')
const assert = require('node:assert/strict')
const fs = require('node:fs')

test('news detail page renders translated body with original title but without original body', () => {
  const pageWxml = fs.readFileSync('pages/news/detail.wxml', 'utf8')
  const readerWxml = fs.readFileSync('components/article-reader/article-reader.wxml', 'utf8')
  const readerJs = fs.readFileSync('components/article-reader/article-reader.js', 'utf8')

  assert.match(pageWxml, /<article-reader/)
  assert.match(pageWxml, /article="\{\{article\}\}"/)
  assert.match(readerJs, /article\.bodyBlocksZh\s*\|\|\s*article\.bodyBlocks/)
  assert.match(readerJs, /labeledText\('原题：', article\.originalTitle\)/)
  assert.match(readerWxml, /originalTitleText/)
  assert.doesNotMatch(pageWxml + readerWxml + readerJs, /article\.originalBody/)
  assert.doesNotMatch(pageWxml + readerWxml + readerJs, /original-panel/)
})

test('news detail renders Chinese tag chips and a compact source footer', () => {
  const readerWxml = fs.readFileSync('components/article-reader/article-reader.wxml', 'utf8')
  const readerCss = fs.readFileSync('components/article-reader/article-reader.wxss', 'utf8')
  const readerJs = fs.readFileSync('components/article-reader/article-reader.js', 'utf8')

  assert.doesNotMatch(readerWxml, /detail-info-grid/)
  assert.doesNotMatch(readerWxml, /资讯 ID/)
  assert.doesNotMatch(readerWxml, /重要度/)
  assert.match(readerJs, /article\.metaChips\s*\|\|\s*article\.tagItems/)
  assert.match(readerWxml, /metaChips/)
  assert.match(readerWxml, /wow-article-reader__source-footer/)
  assert.match(readerWxml, /复制来源链接/)
  assert.match(readerCss, /\.wow-article-reader__chip[\s\S]*font-size:\s*20rpx/)
  assert.match(readerCss, /\.wow-article-reader__source-footer[\s\S]*grid-template-columns:\s*minmax\(0,\s*1fr\)\s*176rpx/)
})

test('news detail renders source trust badges and body block styles for mobile reading', () => {
  const readerWxml = fs.readFileSync('components/article-reader/article-reader.wxml', 'utf8')
  const readerCss = fs.readFileSync('components/article-reader/article-reader.wxss', 'utf8')

  assert.match(readerWxml, /sourceBadges/)
  assert.match(readerWxml, /wow-article-reader__body-heading/)
  assert.match(readerWxml, /wow-article-reader__body-list/)
  assert.match(readerWxml, /wow-article-reader__body-quote/)
  assert.match(readerCss, /\.wow-article-reader__body-paragraph[\s\S]*font-size:\s*(27|28|29)rpx/)
  assert.match(readerCss, /\.wow-article-reader__body-paragraph[\s\S]*line-height:\s*1\.(5[5-9]|6[0-9]|7[0-5])/)
})

test('news detail labels the published date instead of showing a bare date', () => {
  const readerWxml = fs.readFileSync('components/article-reader/article-reader.wxml', 'utf8')
  const readerJs = fs.readFileSync('components/article-reader/article-reader.js', 'utf8')

  assert.match(readerJs, /labeledText\('发布时间 ', article\.publishedAt\)/)
  assert.match(readerWxml, /publishedAtText/)
  assert.doesNotMatch(readerWxml, /<text class="detail-date">\{\{article\.publishedAt\}\}<\/text>/)
})

test('news detail clears loading even when the detail request rejects', () => {
  const js = fs.readFileSync('pages/news/detail.js', 'utf8')

  assert.match(js, /requestArticleDetail\(articleId\)[\s\S]*\.catch\(/)
  assert.match(js, /\.finally\(\(\)\s*=>\s*{[\s\S]*loading:\s*false/)
})

test('news detail does not treat summary as a complete translated body', () => {
  const js = fs.readFileSync('pages/news/detail.js', 'utf8')

  assert.doesNotMatch(js, /bodyZh\s*=\s*article\.bodyZh\s*\|\|\s*article\.summary/)
  assert.match(js, /tagItems/)
})
