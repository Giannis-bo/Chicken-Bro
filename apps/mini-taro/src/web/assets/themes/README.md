# Web 插画主题资源

由内置 image_gen 对用户已确认线稿进行 color-only edit，2026-09-07。仅 Web 消费；伊利丹未纳入。

统一提示词：Color-only edit of this approved minimalist Warcraft illustration. Absolutely preserve all character face likeness, poses, weapon proportions, architecture, composition and thin sparse contour lines exactly. Add restrained coloring using the palette below. Very light flat translucent color fills inside selected existing character clothing/armor/skin and architecture shapes, around 15-25% pigment, keep most paper unpainted. Existing linework remains clearly visible. Match an airy low-saturation light Web background skin, not a full-color poster. Pure white background outside illustration with NO paper texture or overall colored tint; extensive white negative space. No new objects, no new line details, no shading hatching, no saturated colors, no text. Same 1536x1024 landscape framing.

| 文件 | 配色 |
| --- | --- |
| alliance.png | muted Alliance blue, pale slate-blue armor and banners, tiny muted antique gold lion accents |
| maghar.png | muted Maghar earthy brown, brown orc skin, pale tan leather and fortress, charcoal axe |
| forsaken.png | muted undead dark gray, pale ash-gray blue skin, smoky gray cloak and city, faint dusty mauve accents |
| void.png | muted void purple, pale lavender and dusty violet, violet void Sunwell, pale cool skin |
| deathwing.png | black theme translated into pale charcoal-gray washes, gray-black dragon armor, restrained warm ember-orange cracks, pale gray city |
| venom.png | muted poison green, pale sage and olive creature and temple, soft yellow-green venom |

保留原生成 PNG；浏览器用低透明度与轻度去饱和将其融入工作台。缩略图延迟加载，工作台只请求当前主题背景。

## 2026-09-08 轻动效资源

使用内置 image_gen，非 CLI。`maghar-citadel.png` 为现用重绘，旧 `maghar.png` 保留作已确认版本的回退资源；`storm-clouds.png` 为有真实 alpha 的厚云层，供希尔瓦娜斯动效使用。其余角色原图保留；风动使用原图坐标下的局部软遮罩位移，光效为 SVG/CSS 装饰层。

### 格罗姆最终精简提示词

Precise refinement of this illustration for a MINIMAL LINE ART Web background. KEEP EXACT Grom face, full body, raised one hand, huge axe, arm proportion, all subject positions and low-angle fortress scale. Change only line density and texture of the fortress, rocks and clouds: remove at least 80 percent of small brick seams, cracks, rivets, stone texture and incidental architectural marks. Retain only main tower silhouettes, bold outer wall planes, 2 or 3 long perspective seams, huge gate outline and spiked battlements. Clean empty flat stone planes, thin restrained sepia contours. Clouds should be only 3 or 4 broad faint gray-brown shapes with simple outline, NO grain. Ground is simple rocky ledge outline with only a few major facets. Keep pale desaturated brown washes, very white background, sparse minimalist elegance matching the original approved Web illustration. The castle must remain monumental but now expressed through very few clean strokes and pale flat fills. No new objects, no lightning, no lettering. 1536x1024.

输入是以旧 maghar.png 编辑的首轮堡垒放大稿（exec-0ab2581a-9da0-4fd6-abb2-14286fea84b5.png）；最终文件来自 exec-db5d77ae-9e79-41c1-81f9-75a964c5e210.png。

### 厚云层提示词

Use case: illustration-story. Asset: transparent PNG atmospheric cloud layer for an existing minimalist Warcraft Web theme. Draw ONE wide bank of heavy, slowly rolling storm clouds, long horizontal silhouette, gray with a slight desaturated blue-violet undertone, broad layered masses, fine sparse hand drawn contour lines, pale flat watercolor fills, no grain or cross-hatching. Cloud shapes feel weighty and overcast but airy edge softness. No landscape, rain, lightning, objects, letters, or characters. All pixels outside the cloud silhouette MUST be genuinely transparent alpha, no white background, no checkerboard. Cloud occupies the middle horizontal third of a 1536x1024 transparent canvas, soft tapered edges. Restrained low saturation and low contrast suitable as a decorative background that must not compete with text.

最终文件来自 exec-a3ee7511-0fe5-45f6-bca0-6e839d777d19.png。前端使用低透明度，以匹配已确认页面。
