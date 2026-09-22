import { Request, Response } from 'express';
import OpenAI from 'openai';

import { IMAGE_MODEL, DESIGN_SYSTEM_PROMPT, imagePrompt } from '../services/thermalArtwork';

export class AiController {
    static async generateDesign(req: Request, res: Response) {
        try {
            const { prompt } = req.body as {
                prompt?: string;
            };
            if (typeof prompt !== 'string' || !prompt.trim() || prompt.length > 3000) {
                res.status(400).json({ error: 'Please enter a request of 1 to 3000 characters' });
                return;
            }

            if (!process.env.OPENAI_API_KEY) {
                console.error('[AI] Missing OPENAI_API_KEY');
                res.status(503).json({ error: 'AI service not configured (Missing API Key)' });
                return;
            }

            const openai = new OpenAI();

            const moderation = await openai.moderations.create({model: 'omni-moderation-latest', input: prompt});
            if (moderation.results.some(result => result.flagged)) {
                res.status(400).json({error: 'Please choose a family-friendly idea.'}); return;
            }

            // 1. Refine Prompt with GPT-4o
            const completion = await openai.chat.completions.create({
                model: "gpt-4o",
                messages: [
                    { role: "system", content: DESIGN_SYSTEM_PROMPT },
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


            // 2. Generate thermal artwork with GPT Image 2.5 Flare.
            const imageResponse = await openai.images.generate({
                model: IMAGE_MODEL,
                prompt: imagePrompt(prompt, designSpecs),
                n: 1,
                size: "1024x1024",
                quality: "medium",
                output_format: "png",
                background: "opaque"
            });

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
