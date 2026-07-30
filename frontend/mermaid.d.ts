declare module "mermaid" {
  const mermaid: {
    initialize: (config: Record<string, unknown>) => void;
    run: (config?: { querySelector?: string; nodes?: Iterable<HTMLElement> }) => Promise<void>;
  };
  export default mermaid;
}
