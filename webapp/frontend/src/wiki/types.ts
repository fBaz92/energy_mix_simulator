export interface WikiDoc {
  slug: string;
  title: string;
  category: string;
  order: number;
  body: string;
}

export interface WikiCategory {
  name: string;
  docs: WikiDoc[];
}

export type WikiIndex = WikiCategory[];
