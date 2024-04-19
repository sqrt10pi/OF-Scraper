import itertools

import cloup as click

import ofscraper.utils.args.groups.common_args as common
import ofscraper.utils.args.helpers as helpers


@click.command(
    "api",
    help="Manually hit api",
    short_help="Manually hit api",
)
@click.option(
    "-m",
    "--method",
    help="HTTP Method",
)
@click.option(
    "-u",
    "--url",
    help="Endpoint URL",
)
@common.common_params
@common.common_other_params
@click.pass_context
def api(ctx, *args, **kwargs):
    return ctx.params, ctx.info_name
