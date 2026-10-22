type Falsy = false | null | undefined | 0 | '';

export function cn(...inputs: (string | Falsy)[]): string {
  return inputs
    .filter((x): x is string => typeof x === 'string' && x.length > 0)
    .join(' ');
}