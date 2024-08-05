import type {
    GroupedOptions,
    SelectGrouped,
    SelectOption,
    SelectOptions,
} from "@goauthentik/elements/types.js";

type Pair = [string, SelectOption];
const mapPair = (option: SelectOption): Pair => [option[0], option];

const isSelectOptionsArray = (v: unknown): v is SelectOption[] => Array.isArray(v);

// prettier-ignore
const isGroupedOptionsCollection = (v: unknown): v is SelectGrouped =>
    v !== null && typeof v === "object" && "grouped" in v && v.grouped === true;

export const groupOptions = (options: SelectOptions): GroupedOptions =>
    isSelectOptionsArray(options) ? { grouped: false, options: options } : options;

export function optionsToFlat(options: GroupedOptions): Pair[] {
    return isGroupedOptionsCollection(options)
        ? options.options.reduce(
              (acc: Pair[], { options }): Pair[] => [...acc, ...options.map(mapPair)],
              [] as Pair[],
          )
        : options.options.map(mapPair);
}

export function findFlatOptions(options: Pair[], value: string): Pair[] {
    const fragLength = value.length;
    return options.filter((option) => (option[1][1] ?? "").substring(0, fragLength) === value);
}

export function findOptionsSubset(options: GroupedOptions, value: string): GroupedOptions {
    const fragLength = value.length;
    if (value.trim() === "") {
        return options;
    }

    const optFilter = (options: SelectOption[]) =>
        options.filter((option) => (option[1] ?? "").substring(0, fragLength) === value);

    if (options.grouped) {
        return {
            grouped: true,
            options: options.options
                .map(({ name, options }) => ({
                    name,
                    options: optFilter(options),
                }))
                .filter(({ options }) => options.length !== 0),
        };
    }

    return {
        grouped: false,
        options: optFilter(options.options),
    };
}
