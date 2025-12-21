import { Request, Response } from 'express';
import OpenAI from 'openai';

const THERMAL_SYSTEM_PROMPT = `You are a designer for a thermal receipt printer used for intimate family notes.

Your job is to create PRINT-READY artwork and layouts that will be printed on a black-and-white thermal printer.

CRITICAL CONSTRAINTS:
- Output must be black and white only (no grayscale, no color).
- Maximum width is exactly 576 pixels.
- Height can vary but should be as compact as possible.
- Background must be white.
- Artwork must print clearly on thermal paper:
  - Use bold lines
  - Avoid fine details
  - Avoid large dark filled areas
- Favor simple line art, icons, doodles, and high-contrast typography.

STYLE GUIDELINES:
- Warm, gentle, hand-made, human.
- Suitable for children and family.
- Never creepy, scary, or overly realistic.
- Think: refrigerator note, lunchbox drawing, bedtime doodle.
- Slight imperfections are good.

CONTENT GUIDELINES:
- Assume the sender is a father.
- The recipient may be a child or partner.
- Tone should feel loving, reassuring, and calm.
- Avoid sarcasm or irony.

OUTPUT FORMAT:
Return a single JSON object with:
- "image_prompt": a concise internal description of the image to generate
- "layout_description": how text and image are arranged vertically
- "suggested_caption" (optional): short text to include
- "style_tags": list of tags like ["line_art", "doodle", "bedtime"]
- "generation_instructions": explicit instructions to constrain the image generator

DO NOT mention printers, pixels, or technical details in the image content itself.
DO NOT include any explanatory text outside the JSON.`;

export class AiController {
    static async generateDesign(req: Request, res: Response) {
        try {
            const { prompt } = req.body as {
                prompt?: string;
            };
            if (!prompt) {
                res.status(400).json({ error: 'Prompt is required' });
                return;
            }

            if (!process.env.OPENAI_API_KEY) {
                console.error('[AI] Missing OPENAI_API_KEY');
                res.status(503).json({ error: 'AI service not configured (Missing API Key)' });
                return;
            }

            const openai = new OpenAI();

            console.log('[AI] Generating design for:', prompt);

            // 1. Refine Prompt with GPT-4o
            const completion = await openai.chat.completions.create({
                model: "gpt-4o",
                messages: [
                    { role: "system", content: THERMAL_SYSTEM_PROMPT },
                    {
                        role: "user",
                        content: `User wants to create the following message: "${prompt}"`
                    }
                ],
                response_format: { type: "json_object" }
            });

            let designSpecs;
            try {
                const content = completion.choices[0].message.content || '{}';
                designSpecs = JSON.parse(content);
            } catch (e) {
                console.error('[AI] Failed to parse design specs:', completion.choices[0].message.content);
                throw new Error('AI returned invalid design specifications');
            }

            console.log('[AI] Design Specs:', designSpecs);

            // 2. Generate Image with DALL-E 3 (or gpt-image-1.5 if available)
            const imagePrompt = [
                "Black and white thermal printer line art. Simple, bold lines. No shading. No grayscale. White background.",
                designSpecs.image_prompt,
                designSpecs.generation_instructions
            ].filter(Boolean).join(' ').trim();

            console.log('[AI] Generating image...');
            console.log('[AI] Prompt:', imagePrompt);

            const imageResponse = (await openai.images.generate({
                model: "dall-e-3", // Reverting to dall-e-3 as it's more standard if gpt-image-1.5 was causing issues
                prompt: imagePrompt,
                n: 1,
                size: "1024x1024",
                quality: "standard",
                response_format: "b64_json"
            } as any)) as any;

            if (!imageResponse.data || !imageResponse.data[0]) {
                console.error('[AI] No image data in response:', JSON.stringify(imageResponse));
                throw new Error('No image data returned from OpenAI');
            }

            const rawBase64 = imageResponse.data[0].b64_json;
            if (!rawBase64) {
                console.error('[AI] Missing b64_json in response data:', JSON.stringify(imageResponse.data[0]));
                throw new Error('Image data was not returned in base64 format');
            }

            res.json({
                image: `data:image/png;base64,${rawBase64}`,
                caption: designSpecs.suggested_caption,
                specs: designSpecs
            });

        } catch (error: any) {
            console.error('[AI] Generation failed:', error);
            const errorMessage = error.message || 'AI generation failed';
            const errorStatus = error.status || error.response?.status || 500;
            const errorDetails = error.error || error.response?.data || error.data || null;

            res.status(errorStatus).json({
                error: errorMessage,
                details: errorDetails
            });
        }
    }
}
